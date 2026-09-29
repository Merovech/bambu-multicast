```
P2S (built-in cam, LAN mode) ───────────┬──────────────────┐
                                        │                  │
A1 (LAN mode: status/control) ─────┬────┼──────────────────┤
                                   │    │                  │
Logitech C920 (USB, aimed at the   │    │                  │
  A1's build plate — plugs into    │    │                  │
  the Pi, not the A1) ─────┐       │    │                  │
                           ▼       ▼    ▼                  ▼
                    Raspberry Pi 4B (Raspberry Pi OS Lite 64-bit)
                    ├─ ustreamer          (C920 → local MJPEG :8081, for the A1)
                    ├─ go2rtc             (P2S's own RTSP camera → local MJPEG
                    │                      :1984, pulled directly over the LAN)
                    ├─ Bambu Connect #1   (OctoEverywhere companion — P2S:
                    │                      status/control only, separate from
                    │                      go2rtc's camera connection above)
                    ├─ Bambu Connect #2   (OctoEverywhere companion — A1, using
                    │                      ustreamer's feed as its "Alternative
                    │                      Webcam" instead of the A1's own camera)
                    ├─ combined-view page (static HTML, two <img> tags pointing
                    │                      at the two local MJPEG streams above —
                    │                      served by Python's http.server)
                    └─ cloudflared        (outbound-only tunnel, no port forwarding,
                                            no exposed WAN IP)
                               │
                               ▼
                    Cloudflare (path-based routing on ariroth.com,
                                Universal SSL terminates HTTPS at the edge)
                               │
                               ▼
                    https://ariroth.com/printers/  (public, no login)
```

Why this shape, not "just use OctoEverywhere's own dashboard":

- **Bambu Connect** is OctoEverywhere's standalone companion for Bambu Lab
  printers — it does *not* need OctoPrint. It talks to each printer over
  Bambu's local **LAN mode** API. You run one instance per printer, and
  multiple instances can live on a single Pi 4.
  ([setup guide](https://blog.octoeverywhere.com/setup-bambu-connect-for-bambu-lab-3d-printers-on-a-raspberry-pi/),
  [help article](https://help.octoeverywhere.com/knowledge-base/bambu-lab-3-d-printers/bambu-connect-raspberry-pi-setup))
- **A1 webcam:** Bambu Connect supports an "**Alternative/External Webcam**"
  setting per printer — you point it at any local MJPEG/RTSP source instead of
  the printer's own camera. That's exactly the C920-instead-of-built-in-camera
  setup you want, and it also gets you full frame rate instead of the A1's
  built-in camera's 1 FPS. **The C920 plugs into the Pi, not the A1** — the A1
  has no USB port for this, and the printer and camera never talk to each
  other directly. The C920 just needs to be physically aimed at the A1's
  build plate, with a USB cable (extension if needed) run back to the Pi. The
  A1 itself only ever exchanges LAN-mode status/control traffic with its
  Bambu Connect instance; the video path is entirely separate
  (camera → Pi → OctoEverywhere), and OctoEverywhere just displays the two
  side by side as if the video came from the printer.
  ([external webcam setup](https://help.octoeverywhere.com/knowledge-base/bambu-lab-3-d-printers/external-alternative-webcam-setup))
- **P2S webcam, and the combined page:** OctoEverywhere's own multi-printer
  dashboard (octoeverywhere.com/dashboard) *does* show all your printers on
  one page — but it sits behind your OctoEverywhere account login, which
  conflicts with your "no login for viewers" requirement. Their **Live
  Links** feature gives a public, no-login link per printer, but that's one
  printer per link, and it's unconfirmed whether their pages can be embedded
  in an `<iframe>` on another domain. OctoEverywhere also has a **Plugin API**
  that can supposedly serve multi-cam snapshots/streams, but in practice its
  public documentation doesn't go deep enough to write reliable, verified
  code against it. Rather than build your combined page around any of that,
  the plan pulls both camera feeds **directly over your own LAN, with no
  cloud service involved at all**: the A1's feed already runs locally via
  ustreamer (Phase 3); the P2S gets the same treatment via **go2rtc**, a small
  program that connects straight to the P2S's own built-in camera server
  (Bambu printers expose this locally over RTSP, independent of any Bambu or
  OctoEverywhere cloud account) and republishes it as local MJPEG, the same
  format ustreamer already produces for the A1. The combined page then
  becomes a static HTML file with two `<img>` tags — no API key, no
  server-side code, nothing to authenticate, and nothing that depends on a
  third party's undocumented behavior.
  ([go2rtc](https://github.com/AlexxIT/go2rtc))
- **Cloudflare Tunnel** avoids opening any port on your Ziply router, avoids
  exposing your home IP, and gets you HTTPS for free via Cloudflare's edge
  certificate — no certbot/Let's Encrypt renewal cron job to maintain. Tunnel
  ingress rules can match on **path**, so `/printers/*` can route to the Pi
  while the rest of `ariroth.com` is untouched.