// Polls /status.json every few seconds and fills in each printer's card.
// Expects status_server.py to return, per printer: gcode state, printer state, 
// model, percent, layer, total_layers, remaining_seconds, eta_utc, and (on error) 
// error.
//
// Note: this is not meant to be particularly complicated, so no React, Next.js, etc.
// it *could* be done with one of those, without a doubt, but this is just for a
// simple one-page site.

// Change this to poll more frequently.  Higher means more frequent updates and more
// accurate from second-to-second, but requires more calls from the browser.  Lower
// is the opposite.  The value is in milliseconds.  5000 is the default and is
// overwritten by the config the first time it comes from the python server.
let pollIntervalMs = 5000;

function formatDuration(totalSeconds) {
  const s = Math.max(0, Math.round(totalSeconds || 0));
  const hh = String(Math.floor(s / 3600)).padStart(2, "0");
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

function setField(card, name, value) {
  const el = card.querySelector(`[data-field="${name}"]`);
  if (el) {
    el.textContent = value;}
}

// Block of HTML that gets rendered.  If you want to tweak the cards to taste,
// this is where you do it.  This prevents us from having to copy and paste
// cards when you have many streams, as well as maintain any changes across them.
function renderCard({ id, label, cameraUrl }) {
  return `
    <div class="flex-1 basis-[480px] max-w-[640px]" data-printer="${id}">
      <h2 class="my-2 text-center text-lg font-normal">${label}</h2>

      <div class="relative aspect-video">
        <img class="block w-full h-full rounded-lg bg-black object-cover" src="${cameraUrl}" data-base-src="${cameraUrl}" alt="${label} camera" data-role="camera-img">
        <div class="absolute inset-0 flex items-center justify-center" data-role="camera-spinner">
          <div class="h-8 w-8 animate-spin rounded-full border-4 border-neutral-600 border-t-neutral-300"></div>
        </div>
      </div>

      <div class="mt-3 flex min-h-40 items-center justify-center rounded-xl border border-white/10 bg-white/5 p-3 text-center text-sm text-neutral-400" data-role="idle">Idle</div>

      <div class="mt-3 hidden min-h-40 rounded-xl border border-white/10 bg-white/5 p-3 text-sm" data-role="detail">
        <div class="mb-2 text-neutral-300"><span class="font-bold">Model:</span> <span data-field="model">—</span></div>

        <div class="flex items-center justify-between gap-4">
          <div class="flex"><span class="text-lg font-semibold text-[#4caf50]" data-field="percent">0%</span></div>
          <div class="text-neutral-300 flex gap-2">
            <span>
              <span class="font-bold">Layer:</span> <span data-field="layer">0</span>/<span data-field="total_layers">0</span>
            </span>
            <span class="font-bold">Remaining:</span> <span data-field="remaining">00:00:00</span>
          </div>
        </div>

        <div class="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-neutral-700">
          <div class="h-full rounded-full bg-[#4caf50] transition-all duration-1000" data-role="bar" style="width: 0%"></div>
        </div>

        <div class="mt-2 flex items-center justify-between text-neutral-300">
          <div>
            <span>
              <span class="font-bold">Status:</span> <span data-field="pstate">-</span>
            </span>
          </div>
          <div><span class="font-bold">Estimated completion:</span> <span data-field="eta">—</span></div>
        </div>

        <div class="mt-2 hidden text-red-400" data-role="error-row">
          <span class="font-bold">Error:</span> <span data-field="error"></span>
        </div>
      </div>
    </div>
  `;
}

// Filled in by loadConfig() below; refreshStatus() polls exactly these IDs,
// so adding a printer to status_server.py's PRINTERS is the only change
// needed to get a new card that's also kept up to date.
let printerIds = [];

// If a stream errors out outright (e.g. it 502s immediately), retry this
// fast. This is just a fast path -- see CAMERA_WATCHDOG_MS below for why it
// can't be the only mechanism.
const CAMERA_ERROR_RETRY_MS = 3000;

// How often to force a brand-new connection regardless of whether an
// "error" event ever fires. Essentially, the streams are somewhat fragile,
// and a small network blip can kill it.  This will force the site to reconnect
// on a fixed interval, which will reconnect to the stream if it was lost.
const CAMERA_WATCHDOG_MS = 30000;

function cacheBustedCameraUrl(baseUrl) {
  // Ensure the browser doesn't cache the camera.
  return `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}_retry=${Date.now()}`;
}

function startCameraStream(img, spinner) {
  const baseUrl = img.dataset.baseSrc;
  const hideSpinner = () => setHidden(spinner, true);

  img.addEventListener("load", hideSpinner);
  img.addEventListener("error", () => {
    hideSpinner();
    setTimeout(() => {
      img.src = cacheBustedCameraUrl(baseUrl);
    }, CAMERA_ERROR_RETRY_MS);
  });

  setInterval(() => {
    img.src = cacheBustedCameraUrl(baseUrl);
  }, CAMERA_WATCHDOG_MS);
}

async function loadConfig() {
  // Deliberately relative (no leading "/"): this page can be loaded either
  // at the site root (local testing) or under /printers/ (via the
  // Cloudflare Tunnel ingress rule).
  const res = await fetch("config.json", { cache: "no-store" });
  const config = await res.json();
  const container = document.getElementById("printers");

  if (config.settings?.poll_interval_ms) {
    pollIntervalMs = config.settings.poll_interval_ms;
  }

  // Page-wide, set-once value.  Not tied to any printer.
  const pollIntervalEl = document.querySelector('[data-field="pollIntervalMs"]');
  if (pollIntervalEl) {
    pollIntervalEl.textContent = pollIntervalMs;
  }

  const printers = config.printers;
  printerIds = Object.keys(printers);
  container.innerHTML = printerIds
    .map((id) => renderCard({ id, label: printers[id].label, cameraUrl: printers[id].camera_url }))
    .join("");

  // Hide each camera's spinner once its first frame actually arrives (or
  // once it's clear the stream failed, so it doesn't spin forever), and
  // keep the stream alive if it ever dies later.
  for (const id of printerIds) {
    const card = document.querySelector(`[data-printer="${id}"]`);
    const img = card.querySelector('[data-role="camera-img"]');
    const spinner = card.querySelector('[data-role="camera-spinner"]');
    startCameraStream(img, spinner);
  }
}

// Tailwind CSS hides elements via class name, not via HTML "hidden attribute"
function setHidden(el, hidden) {
  el.classList.toggle("hidden", hidden);
}

function updateCard(id, info) {
  const card = document.querySelector(`[data-printer="${id}"]`);
  if (!card) {
    return;
  }

  // Get the elements to play with
  const idleEl = card.querySelector('[data-role="idle"]');
  const detailEl = card.querySelector('[data-role="detail"]');
  const bar = card.querySelector('[data-role="bar"]');
  const errorRow = card.querySelector('[data-role="error-row"]');

  // Keep the display simple: if the printer is in Idle mode according to the
  // gcode status, show the idle display.  If it's in Running mode, show the
  // cards.  Printer status (Printing, Homing toolhead, Heating bed, etc.) are
  // for display only -- it's the gcode Idle/Running/Unknown statuses that are
  // the important parts for determining which view to show.
  const isIdle = !info || info.state === "IDLE" || info.state === "UNKNOWN";

  setHidden(idleEl, !isIdle);
  setHidden(detailEl, isIdle);
  if (isIdle) {
      return;
  }

  setField(card, "model", info.model || "Unknown");
  setField(card, "percent", `${info.percent ?? 0}%`);
  setField(card, "layer", info.layer ?? 0);
  setField(card, "total_layers", info.total_layers ?? 0);
  setField(card, "remaining", formatDuration(info.remaining_seconds));
  setField(card, "pstate", info.pstate);
  
  // Show time in the users's current time zone
  const etaText = info.eta_utc
    ? new Date(info.eta_utc).toLocaleString([], { dateStyle: "short", timeStyle: "short" })
    : "—";
  setField(card, "eta", etaText);

  if (bar) {
    bar.style.width = `${info.percent ?? 0}%`;
  }

  if (info.error) {
    setHidden(errorRow, false);
    setField(card, "error", info.error);
  } else {
    setHidden(errorRow, true);
  }
}

async function refreshStatus() {
  try {
    // Relative for the same reason as loadConfig()'s fetch above.
    const res = await fetch("status.json", { cache: "no-store" });
    const data = await res.json();
    for (const id of printerIds) {
      updateCard(id, data[id]);
    }
  } catch (e) {
    console.error("status fetch failed", e);
  }
}

function setPageTitleDate() {
  const titleEl = document.getElementById("page-title");
  if (titleEl) {
    // toLocaleDateString(): the viewer's own browser date, same convention
    // as the ETA formatting above -- never a date computed on the server.
    titleEl.textContent = `Printer Status: ${new Date().toLocaleDateString()}`;
  }
}

async function main() {
  setPageTitleDate();
  try {
    await loadConfig();
  } catch (e) {
    console.error("failed to load /config.json", e);
    return;
  }
  refreshStatus();
  setInterval(refreshStatus, pollIntervalMs);
}

main();
