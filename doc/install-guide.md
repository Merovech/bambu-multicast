# Bambu Multicast Setup Guide

<details open>
<summary>Table of Contents</summary>

- [Bambu Multicast Setup Guide](#bambu-multicast-setup-guide)
  - [Architecture](#architecture)
  - [Supported printers](#supported-printers)
  - [Requirements](#requirements)
    - [Hardware](#hardware)
    - [Software](#software)
    - [Other](#other)
  - [Let's get started](#lets-get-started)
    - [Phase 0 — Set up your printers](#phase-0--set-up-your-printers)
    - [Phase 1 — Set up your Pi](#phase-1--set-up-your-pi)
    - [Phase 2 — Install Bambu Connect](#phase-2--install-bambu-connect)
    - [Phase 3 — External webcam (Optional)](#phase-3--external-webcam-optional)
    - [Phase 4 — Get the printer's camera onto the local network via go2rtc](#phase-4--get-the-printers-camera-onto-the-local-network-via-go2rtc)
    - [Phase 5 — Build the combined-view page](#phase-5--build-the-combined-view-page)
      - [A. Camera-only page first](#a-camera-only-page-first)
      - [B. Add progress, layer, and ETA](#b-add-progress-layer-and-eta)
      - [C. Turn it into one systemd service](#c-turn-it-into-one-systemd-service)
    - [Phase 6 — Cloudflare Tunnel: publish to ariroth.com/printers/](#phase-6--cloudflare-tunnel-publish-to-arirothcomprinters)
    - [Phase 7 — Hardening / polish](#phase-7--hardening--polish)
    - [Phase 8 — Tune once it's live (do later, with real traffic)](#phase-8--tune-once-its-live-do-later-with-real-traffic)
  - [Reference links](#reference-links)
</details>

Bambu Multicast (BM) is a companion for Bambu Lab 3D printers that lets you show multiple live streams of your printers on one web site.  This project began when I got tired of needing two copes of Bambu Studio open in order to monitor jobs on both of my printers simultaneously.

Multicast is largely intended for people who want to view this on a website without having a lot of technical knowledge.  The code is designed to require minimal changes -- if any -- and can be deployed and configured without any knowledge of CSS, HTML, JavaScript, or Python.

In fact, you can go through this guide and deploy without ever opening any file other than a few configs, and we will walk you through that.

> [!IMPORTANT] 
> This document covers installing BM on a Raspberry Pi.  However, any Linux-based machine will do.  Windows is currently not supported, though it may be in the future.
>
> If you're of a more technical bent, I'm sure this could probably be installed on Windows using WSL, but I haven't tried it yet.

##  <a name='Architecture'></a>Architecture
If you happen to be curious about the architecture of BM -- both hardware and software -- see [architecture.md](architecture.md), in this folder.

##  <a name='Supportedprinters'></a>Supported printers

If you want to use your printer's built-in camera, any BambuLab printer supported by OctoEverywhere is supported by BM.

If you want to use a webcam pointed at your printer, then any webcam that can work with `go2rtc` and `ffmpeg` will do.

##  <a name='Requirements'></a>Requirements
> [!NOTE]
> All links are examples.  I am not affiliated or endorsed by anyone.
###  <a name='Hardware'></a>Hardware
* One or more BambuLab printers
* Raspberry Pi 4B or later ([PiShop](https://www.pishop.us/product/raspberry-pi-4b-budget-kit/))
  * 4GB is good for a 2-printer setup, but more RAM allows for more printers or higher-quality streams
* A MicroSD card that will serve as the hard drive for the Pi ([Amazon](https://www.amazon.com/dp/B08L5HMJVW))
  * 32GB is recommended
* (For external webcams) A webcam ([Amazon](https://www.amazon.com/)Logitech-C920x-Pro-HD-Webcam/dp/B085TFF7M1/)
* The ability to write to a Micro SD card
  * If your computer doesn't have a built-in jack, there are several adapter options out there: [MicroSD to SD](https://www.amazon.com/SanDisk-microSD-Memory-Adapter-MICROSD-ADAPTER/dp/B0047WZOOO), [SD/MicroSD to USB](https://www.amazon.com/acer-Adapter-MicroSD-Compatible-iPhone16/dp/B0DQ71G4G4)
###  <a name='Software'></a>Software
* [Raspberry Pi Imager](https://www.raspberrypi.com/software/) so you can install an OS on the Pi, which comes without one preinstalled

All other software is installed for free over the course of this guide.
###  <a name='Other'></a>Other
* An accocunt on [OctoEverywhere](https://octoeverywhere.com/)
* Admin-level access to the Pi -- we will use `sudo` a lot

##  <a name='Letsgetstarted'></a>Let's get started
###  <a name='Phase0Setupyourprinters'></a>Phase 0 — Set up your printers

1. Update your printers' firmware
2. Enable **LAN Mode** on your printers.
> [!IMPORTANT]
> This will disconnect your printers from the cloud, meaning some features -- includng using the Bambu Handy app -- will no longer work.  Bambu Studio will, however.  For further details, see [here](https://wiki.bambulab.com/en/knowledge-sharing/enable-lan-mode).
3. Write down or otherwise record each printer's **Access Code** and **IP Address**.  You will need these later. 
4. (Optional) Set DHCP IP reservations for your printer on your network so that the IP addresses never change.

> [!TIP]
> The last step is optional but **highly recommended**.  Doing this keeps the system stable in thge event of a power outage, router reboot, etc.  If you do not do this, then whenever your printers' IP changes, Bambu Multicast will break until you update the configuration with the new IP.

###  <a name='Phase1SetupyourPi'></a>Phase 1 — Set up your Pi
> [!NOTE]
> This document assumes you are using a Raspberry Pi 4 Model B.
1. Insert your SD card into your computer
2. Open Raspberry Pi Imager
3. Select **Raspberry Pi 4** and click Next
4. Select **Raspberry Pi OS (64-bit)** and click Next
5. Select the SD card you inserted in step 1 and click Next
6. In the following screens, give it a hostname of your choice, enable SSH, set a username and password of your choice, and connect it to your LAN.
    * The username and password you create here will be your **Admin password** and will be used whenever logging into the Pi or running a command via `sudo`.
    * All other settings can be left as-is
7. Complete the wizard to flash your SD card
8. Put the SD card into the Pi
9. Plug the Pi in -- there is no on/off switch, so this will cause it to boot
10. Wait 30 seconds or so, since you won't have a monitor connected and have to guess when the boot is complete
11. Make sure `apt` is up-to-date.  This is the package manager we will use.
    * Open a command-line window on your non-Pi computer
    * Type `ssh` and press Enter
    * Enter the username/password you created in step 6.  You should now be logged into your Pi.
    * Type `sudo apt update && sudo apt full-upgrade -y` and press Enter
    * Enter your password, press Enter, and let it run.  This may take a moment.
12. (Optional) Set DHCP IP reservations for your Pi on your network so that its IP address never change.

> [!TIP]
> The last step is optional but **highly recommended**.  Doing this keeps the system stable in thge event of a power outage, router reboot, etc.  If you do not do this, then whenever your Pi's IP changes, so will the address of the website you are setting up.

###  <a name='Phase2InstallBambuConnect'></a>Phase 2 — Install Bambu Connect
> [!IMPORTANT]
> This phase will need to be repeated once for each printer you intend to use.

> [!NOTE]
> In this step you will be installing the Bambu Connect software and telling OctoEverywhere about the printers.  Don't worry if OctoEverywhere shows the printer's built-in camera when you want to use an external camera; will fix that in Phase 3, next.
1. Run `bash <(curl -s https://octoeverywhere.com/bambu.sh)`
2. Follow the prompts the script walks you through.
3. Open the OctoEverywhere web portal and confirm that your printer shows up and reports its current status (e.g., temperatures, state, etc.)

###  <a name='Phase3ExternalwebcamOptional'></a>Phase 3 — External webcam (Optional)
> [!IMPORTANT]
> This phase will need to be repeated once per external camera you use.  If you are not using one, skip it.  If you do this more than once, don't forget to change the port number for each one!
>
> This document assumes you are using a Logitech C920 camera.  Your output may vary slightly dependinig on thge model you use.

1. Plug the webcam into the Pi
2. Verify the camera is detected with the following commands.  Your camera should show up as `/dev/video[X]` and `/dev/video[X+1]`, e.g., `/dev/video0` and `/dev/video1`.
```
sudo apt install -y v4l-utils
v4l2-ctl --list-devices
```
3. Get the camera's stable device path by calling `ls -l /dev/v4l/by-id`.  Write down  the result; you will need it later.  Your camera should show up in a format similar to the following:
```
lrwxrwxrwx 1 root root 12 Sep 20 17:19 usb-046d_HD_Pro_Webcam_C920_6C60D16F-video-index0 -> ../../video0
lrwxrwxrwx 1 root root 12 Sep 20 17:19 usb-046d_HD_Pro_Webcam_C920_6C60D16F-video-index1 -> ../../video1
```
4. Install ustreamer
```
sudo apt update
sudo apt install -y ustreamer
```
5. Add your user to the `video` group ($USER is the username you created for the Pi)
```
sudo usermod -aG video $USER
```
6. Log out and log back into the Pi to ensure your user account now has the correct permissions
7. (Optional, but recommended) Test everything by hand to make sure everything works, using the stable device path in step 3 for $DEVICE
    1. On the Pi, run the following command: `
ustreamer --device=$DEVICE --host=0.0.0.0 --port=8081 --resolution=1280x720 --format=MJPEG --workers=3`
    2. On a different computer, open your web browser to `http://$PI_IP:8081/stream`, where $PI_IP is the IP address of your PI; you should see the printer streaming
    3. On the Pi, press CTRL+C to stop ustreamer

> [!NOTE]
> You may see a warning on the Pi: `Device doesn't support setting of HW encoding quality parameters`.  You can ignore this; it's just noting that the camera's MJPEG encoder doesn't expose a software-adjustable quality control.

8. Create a file at `/etc/systemd/sudo/$NAME.service`, where \$NAME is a unique name to identify that particular camera (e.g., `ustreamer-a1.service`, `ustreamer-p2s.service`, etc.)  Do this with `sudo touch /etc/systemd/system/$NAME.service`.
9. Using nano (`sudo nano /etc/systemd/system/$NAME.service`), copy the text below into the file, then press CTRL+S to save and CTRL+Q to exit (don't forget to modify the text to reflect your stable device path to replace $DEVICE)

```ini
[Unit]
Description=Your description here
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/ustreamer \
      --device=/dev/v4l/by-id/$DEVICE$ \
      --host=0.0.0.0 \
      --port=8081 \
      --resolution=1280x720 \
      --format=MJPEG \
      --workers=3
Restart=always
RestartSec=2
User=pi
Group=video

[Install]
WantedBy=multi-user.target
```
> [!NOTE]
> An explanation of a few fields:
> - `WantedBy=multi-user.target` + `enable` (next step) is what makes it start on boot.
> - `Restart=always` restarts the service no matter *how* it exits (crash, USB hiccup, you `kill`ing it) — not just on nonzero exit codes.
> - `RestartSec=2` waits 2 seconds before each restart attempt, so a persistently failing service doesn't spin the CPU in a tight loop.

> [!IMPORTANT]
> Change `User=pi` to your actual username that you added to the `video` group, or the service will fail with a permissions error.

10. Start the service you just created
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ustreamer-a1.service
```
11. Verify the service is running correctly.  The output should show `active (running)`, and the second command will show live logs; use CTRL+C to stop it and give you a command like back.
```bash
systemctl status ustreamer-a1.service
journalctl -u ustreamer-a1.service -f
```
12. Test the restart-on-failure behavior, don't just trust the config.  You should see a different PID than the one you saw in step 11.
 ```bash
sudo systemctl kill -s SIGKILL ustreamer-a1.service
systemctl status ustreamer-a1.service
```
13. Test the start-on-boot behavior, don't just trust the config.  Reboot (`sudo reboot`).  When you are logged back in `systemctl is-active $NAME.service` should print `active` and the `http://$PI_IP:8081/stream` URL should work again.
14. In the OctoEverywhere portal, open the printer's settings, enable
**Alternative/External Webcam** ([guide](https://help.octoeverywhere.com/knowledge-base/bambu-lab-3-d-printers/external-alternative-webcam-setup)), and point it at `http://localhost:8081/stream` (Bambu Connect for the printer runs on the same Pi, so `localhost` is correct — use the Pi's LAN IP instead only if that instance runs elsewhere, and use the port number you are using for this camera).
15. Confirm the A1's camera feed in the OctoEverywhere portal is now the webcam view, at full frame rate, not the built-in camera.
16. Physically mount/aim the camera as you wish.

###  <a name='Phase4GettheP2Sscameraontothelocalnetworktoogo2rtc'></a>Phase 4 — Get the printer's camera onto the local network via go2rtc

> [!IMPORTANT]
> If you are not using the built-in camera for your printer(s) -- that is, you are ONLY using external cameras -- this step should be skipped.  Otherwise, repeat it once per printer whose camera you are using.

> [!NOTE]
> This section assumes a P2S for the printer, for simplicity.  It's *likely* that other printers will work, but check OctoEverywhere's website for compatibility.  It supports multiple printers, but if you're using one released last week it might not yet.

It turns out that Bambu printers have their own API that can be accessed to get print information, camera streams, etc.  We're going to usee that.

1. Confirm "LAN Mode Liveview" is on for the P2S. This is a *separate* toggle from the general "LAN Mode" you turned on in Phase 0 — in the Bambu Handy app or the printer's touchscreen, find the printer's network settings and enable **LAN Mode Liveview** (sometimes just labeled "Liveview"). This is what allows a direct local video connection to the camera.

2. Sanity-check the camera URL works at all, using the P2S's LAN access code and IP address (the same ones you noted in Phase 0). The URL format Bambu printers use is:
      ```
      rtsps://bblp:<access_code>@<p2s-ip>:322/streaming/live/1
      ```
      `bblp` is always the username, for every Bambu printer. If you want a quick visual check before touching the Pi, open this URL in VLC on any computer: File → Open Network Stream → paste the URL. VLC will warn that the certificate is self-signed/untrusted — that's expected (Bambu
      printers use a self-signed cert here), click through it.

      Web browsers won't accept that URL, so instead you can and should test it on the Pi directly:
      ```
      sudo apt install -y ffmpeg
      ffmpeg -rtsp_transport tcp -i "rtsps://bblp:<access_code>@<p2s-ip>:322/streaming/live/1" -frames:v 1 -y test.jpg
      ```
3. Download go2rtc onto the Pi. It's a single self-contained program -- no installer, no dependencies to install first:
      > [!NOTE]
      > Because this isn't a package, you may need to modfy the URL below.  Double check [here](https://github.com/AlexxIT/go2rtc/releases/).  (Pick the first entry in the release list and use the download URL for `go2rtc_linux_arm64.`)
      ```
      cd ~
      curl -fLo go2rtc https://github.com/AlexxIT/go2rtc/releases/download/v1.9.14/go2rtc_linux_arm64
      file go2rtc
      ```

      Two safety checks are built in here. `-f` makes curl fail loudly instead of saving GitHub's "Not Found" page as if it were the program (which later shows up as `Not: command not found`). And `file go2rtc` must say `ELF 64-bit ... ARM aarch64` — if it says `x86-64`, you grabbed the PC build (`amd64`) instead of `arm64`, which fails later with `Exec format error`. Only continue once it says `aarch64`:
      ```bash
      chmod +x go2rtc
      sudo mv go2rtc /usr/local/bin/go2rtc
      ```
      Confirm it's in place: `go2rtc --version` should print a version number.

4. Make sure ffmpeg is installed, if you haven't yet:
      ```
      sudp apt install -y ffmpeg
      ```
5. Create its config file at `/usr/local/etc/go2rtc.yaml`:
      ```bash
      sudo mkdir -p /usr/local/etc
      sudo nano /usr/local/etc/go2rtc.yaml
      ```
      Paste in (renaming `p2s_raw` and `p2s` to whatever you want, but note it for later):
      ```yaml
      streams:
        p2s_raw: rtspx://bblp:<access_code>@<p2s-ip>:322/streaming/live/1
        p2s: ffmpeg:p2s_raw#video=mjpeg
      ```
      The P2S sends H.264 video, which browsers can't show in an `<img>` tag. go2rtc can't convert formats by itself; it hands the job to ffmpeg, which we installed in the previous step.  The
      first line pulls the printer's feed as-is (`p2s_raw`); the second defines `p2s`, which converts it to MJPEG — that's the name the URLs below use. Without ffmpeg and the second line, go2rtc logs `codecs not matched: video:H264 => video:JPEG`.

      Replace `<access_code>` and `<p2s-ip>` with the P2S's real values. Note the scheme is **`rtspx://`**, not `rtsps://` — that `x` is go2rtc's own convention meaning "RTSP over TLS, but don't validate the certificate," which is exactly what's needed for Bambu's self-signed certificate. (Save/exit in `nano`: Ctrl+O, Enter, then Ctrl+X.)

6. Test it by hand first, before wiring up a system service:
      ```bash
      go2rtc -config /usr/local/etc/go2rtc.yaml
      ```
      Leave it running, and from another machine on your LAN open `http://<pi-ip>:1984/api/stream.mjpeg?src=p2s` (modifying `p2s` to whatever you named it in step 5) — you should see the P2S's live camera feed. (`1984` is go2rtc's built-in default port; you didn't configure that, it just is one.) Once confirmed, `Ctrl+C` to stop it.

7. Create a file at `/etc/systemd/sudo/go2rtc.service`, by using the command `sudo touch /etc/systemd/system/go2rtc.service`.

8. Using nano (`sudo nano /etc/systemd/system/go2rtc.service`), copy the text below into the file, then press CTRL+S to save and CTRL+Q to exit (don't forget to modify the text to reflect your stable device path to replace $DEVICE).  See the systemd primer in Phase 3, Step 9 if any of this is unfamiliar:
      ```ini
      [Unit]
      Description=go2rtc camera server for P2S
      After=network.target

      [Service]
      Type=simple
      ExecStart=/usr/local/bin/go2rtc -config /usr/local/etc/go2rtc.yaml
      Restart=always
      RestartSec=2
      User=pi

      [Install]
      WantedBy=multi-user.target
      ```
      Unlike ustreamer, no `Group=video` is needed — go2rtc isn't opening a local USB device, it's making an outbound network connection to the printer, so no special device permissions apply.

10. Load, start, and verify the new service.
      ```bash
      sudo systemctl daemon-reload # Forces the system to read the .service file
      sudo systemctl enable --now go2rtc.service
      systemctl status go2rtc.service
      ```

11. Prove restart-on-failure and start-on-boot, same drill as Phase 3:
      ```bash
      sudo systemctl kill -s SIGKILL go2rtc.service
      systemctl status go2rtc.service
      ```
      You should get a new PID within ~2 seconds of running the kill command.  To test the reboot behavior, `sudo reboot`, followed by `systemctl is-active go2rtc.service` and reloading the stream URL.

12. You should now have two independent local MJPEG streams running on the Pi:
      - The one(s) from phase 3: `http://<pi-ip>:8081/stream` (altering the port number depending on what you did), and
      - P2S (from this phase): `http://<pi-ip>:1984/api/stream.mjpeg?src=p2s`

      Worth knowing: go2rtc's connection to the P2S is completely separate from Bambu Connect's own connection to that same printer (which OctoEverywhere uses for status/AI-detection). Bambu printers handle a couple of simultaneous *local* viewers fine — this isn't the same as Bambu's *cloud* streaming, which does have a documented low concurrent-viewer limit.

###  <a name='Phase5Buildthecombined-viewpage'></a>Phase 5 — Build the combined-view page

Now we'll build the website itself.  The site is mostly built for you (unless you choose to customize it), as is the small server.  If you choose to go with what is provided, you will only modify config files.

> [!IMPORTANT]
> There are a few *very* important notes to keep in mind here.
>
> * By itself, the site does not require authentication, nor do I intend to add the feature for the time being.  I run this myself on a public URL, and I'm totally fine with someone seeing what I'm printing at any given moment, so I didn't worry about it.  As for HTTP/HTTPS, that is beyond the scope of this document.  Personally, Cloudflare's tunnelling gave it to me for free, so I I didn't build it in here.  If you need HTTPS and the certificates that it requires, you should consult your hosting provider.
> 
> * You are certainly welcome to modify the HTML, JS, and Python as you wish.  My support will be limited: I am willing to support exposing further information to the Python server in the github project, but not custom modifications to the HTML to determine where in a page it is placed.
> 
>     That said, I *am* open to modifying the base site to support theming and including themes in the repository (with credit to the authors, of course!), and I may add it in a future update.  In the meantime, if you need modifications of those sorts (or use modifications and think others will find it useful), open an issue on the project at github and I will make sure it's added.

####  <a name='A.Camera-onlypagefirst'></a>A. Camera-only page first

> **Update:** the page was reworked into three separate files (Tailwind for
> styling, a separate `app.js`, a separate `styles.css`) with a redesigned
> status callout (Model/percent/layer/Remaining/bar/ETA/status/error), then
> wired up to live data. The real, current source is **not** in this
> documentation folder — it lives in the actual project directory,
> `D:\src\printer-site\` (`index.html`, `app.js`, `styles.css`,
> `status_server.py`, plus `upload.sh` for deploying). This folder
> (`...\AI\printer-streaming\`) holds only this punchlist and the original
> `prompt.md` — edit the real files in `D:\src\printer-site\`, not here.
>
> `index.html` loads Tailwind from its CDN (`cdn.tailwindcss.com` — fine for
> a small page with no build step) and starts both cards in a safe idle
> default; `app.js` polls `/status.json` every 5 seconds and fills in the
> detail callout once a print is running.

- [x] **Create the folder on the Pi**, if you haven't already:
      ```bash
      mkdir -p ~/printer-page
      ```
- [x] **Deploy the files to the Pi**, from `D:\src\printer-site\`:
      ```bash
      ./upload.sh
      ```
      (`upload.sh` runs `scp !(*.sh) ari@dionysus:~/printer-page/` — every
      file except itself, so `index.html`, `app.js`, `styles.css`, and
      `status_server.py` all go every time without needing to be listed by
      name.) Verification happens in part B's "test it by hand" step below,
      once `status_server.py` is actually running.

####  <a name='B.AddprogresslayerandETA'></a>B. Add progress, layer, and ETA

The percentage, layer count, and remaining time all come from each printer's
local status feed — a second connection (separate from the camera), using
the same LAN access code, that Bambu printers expose for exactly this
purpose. A small Python library (`bambulabs_api`) handles the details of
that connection; you just call a few methods on it.

- [x] **Find each printer's serial number** (a 15-character code, different
      from the access code) — in the Bambu Handy app, open the printer, go to
      **Settings → Firmware Version**; the serial (SN) is listed there. (It's
      also on a sticker on the printer itself, and viewable via the printer's
      own touchscreen "About" screen.) Note both serials alongside the
      IPs/access codes you already have from Phase 0.

- [x] **Create a Python virtual environment** for this script. Raspberry Pi
      OS Bookworm blocks plain `pip install` system-wide by default (a Debian
      safety measure) — a "virtual environment" is just a self-contained,
      separate copy of Python for one project, which sidesteps that:
      ```bash
      cd ~/printer-page
      python3 -m venv venv
      source venv/bin/activate
      pip install bambulabs-api
      ```
      Your prompt will show `(venv)` while it's active. You can `deactivate`
      to leave it, but you don't need to — the systemd unit later will call
      this venv's Python directly by its full path, without needing it
      "activated."

- [x] **Create the status script** at `~/printer-page/status_server.py`.
      The real, current source is `D:\src\printer-site\status_server.py`
      (not this documentation folder — see the note at the top of part A),
      with your real `PRINTERS` values (IP/access code/serial per printer)
      already filled in. `./upload.sh` (part A) deploys it to the Pi
      alongside the other three files.

      What this does, in plain terms: one background
      thread per printer reconnects and re-reads its status every 5 seconds,
      storing the result in `latest_status`; the web server thread serves
      the page's static files (per `STATIC_FILES`) and one dynamic
      endpoint, `/status.json`, returning whatever the background threads
      most recently saw. `status_lock` just prevents the web server from reading
      `latest_status` at the exact instant a background thread is
      mid-update — a minor safety detail, not something to worry about
      further.

      **Unverified:** `printer.subtask_name()` / `printer.gcode_file()` for
      the "Model" field are the closest-matching methods in the library's
      docs, but I haven't confirmed what either actually returns on a real
      print (a clean name like `Benchy`, a filename like
      `Benchy_v2.3mf`, or something else). Check `status.json` once a print
      is running and adjust if the value looks wrong — e.g. swap which one
      is tried first, or strip a `.3mf`/`.gcode` extension if it's present.

      **Bug found and fixed (2026-09-22):** the detail/error-row blocks
      stayed hidden even once `status.json` had real data. Cause: they're
      hidden in `index.html` by Tailwind's `hidden` **CSS class** (part of
      `class="..."`), but `app.js` was toggling the native `hidden` HTML
      **attribute** (`el.hidden = false`) — same word, two unrelated
      mechanisms, and only the class was actually in effect. Fixed by adding
      a `setHidden(el, hidden)` helper that does
      `el.classList.toggle("hidden", hidden)` instead, used everywhere the
      old code set `.hidden` directly. Worth remembering if any future markup
      adds another Tailwind `hidden` class: toggle it via `classList`, not
      the `.hidden` property.

- [x] **Test it by hand**, with the venv still active from a step above (if
      you closed that terminal, `cd ~/printer-page && source venv/bin/activate`
      again first):
      ```bash
      python3 status_server.py
      ```
      From another machine, reload `http://<pi-ip>:8090/` — the "Loading…"
      text should resolve to either a live percent/layer/ETA line (if a
      print is running) or "Idle" (if not). You can also check the raw data
      directly: `curl http://localhost:8090/status.json` should print JSON
      for both printers. `Ctrl+C` to stop once confirmed.

####  <a name='C.Turnitintoonesystemdservice'></a>C. Turn it into one systemd service

- [ ] **Create the systemd unit** at
      `/etc/systemd/system/printer-page.service` — this replaces the plain
      `http.server` command from part A with the new script, run using the
      **venv's** Python (not the system one, since only the venv has
      `bambulabs_api` installed):
      ```ini
      [Unit]
      Description=Combined printer camera + status page
      After=network.target

      [Service]
      Type=simple
      WorkingDirectory=/home/pi/printer-page
      ExecStart=/home/pi/printer-page/venv/bin/python3 /home/pi/printer-page/status_server.py
      Restart=always
      RestartSec=2
      User=pi

      [Install]
      WantedBy=multi-user.target
      ```
      Replace `/home/pi/printer-page` (it appears twice) with the real path
      if your username isn't `pi` — run `pwd` inside that folder to confirm.
      Using the venv's own `python3` binary is what makes `import
      bambulabs_api` work without needing that package installed
      system-wide.

- [ ] **Load, start, and verify it:**
      ```bash
      sudo systemctl daemon-reload
      sudo systemctl enable --now printer-page.service
      systemctl status printer-page.service
      journalctl -u printer-page.service -f
      ```
      Watch the logs for a moment for any Python errors (a typo'd IP/access
      code/serial would show up here as a connection error from one of the
      background threads).

- [ ] **Prove restart-on-failure and start-on-boot**, same drill as the other
      two services:
      ```bash
      sudo systemctl kill -s SIGKILL printer-page.service
      systemctl status printer-page.service
      ```
      then a real `sudo reboot`, then reload `http://<pi-ip>:8090/`.

- [ ] Load `http://<pi-ip>:8090` from your phone too (same Wi-Fi), to get an
      early look at mobile behavior — including that the ETA should already
      show in your phone's own local time, automatically, with no extra
      work — before debugging any of this live on `ariroth.com` later.

###  <a name='Phase6CloudflareTunnel:publishtoariroth.comprinters'></a>Phase 6 — Cloudflare Tunnel: publish to ariroth.com/printers/

- [ ] Install `cloudflared` on the Pi
      (`sudo apt install cloudflared`, or via Cloudflare's apt repo per their
      current install docs — check `cloudflared --version` after).
- [ ] `cloudflared tunnel login` (opens a browser flow to authorize against
      your Cloudflare account/zone for ariroth.com).
- [ ] `cloudflared tunnel create printers` — note the generated tunnel ID and
      credentials file path.
- [ ] Write `~/.cloudflared/config.yml`:
  ```yaml
  tunnel: printers
  credentials-file: /home/<user>/.cloudflared/<tunnel-id>.json

  ingress:
    - hostname: ariroth.com
      path: ^/printers/.*
      service: http://localhost:8090   # or 8080/whatever your combined view listens on
    - service: http_status:404
  ```
  - **Check first what currently lives at `ariroth.com` root.** If nothing is
    hosted there yet, you can broaden this later to host a real homepage
    elsewhere and let this rule carve out just `/printers/*`. If something
    *is* already hosted there (e.g. via Cloudflare Pages, another tunnel, or
    another server), this path-scoped rule leaves it alone — Cloudflare
    checks the `path`-scoped rule first and only falls through if it doesn't
    match.
- [ ] `cloudflared tunnel route dns printers ariroth.com` (only needed if
      `ariroth.com` doesn't already have a DNS record; if it does, e.g.
      pointing elsewhere via Cloudflare, add/adjust the CNAME to the tunnel
      manually in the Cloudflare DNS dashboard instead, so you don't disturb
      existing records).
- [ ] Install as a service so it survives reboots:
      `sudo cloudflared service install`, then `sudo systemctl enable --now cloudflared`.
- [ ] Confirm Cloudflare SSL/TLS mode for the zone is **Full** (or **Full
      strict** if you later add a cert on the origin) — Universal SSL then
      covers the public-facing HTTPS automatically, no Let's Encrypt/certbot
      needed.
- [ ] From a phone on cellular data (not your home Wi-Fi), load
      `https://ariroth.com/printers/` and confirm both streams load over
      HTTPS with no login prompt.

###  <a name='Phase7Hardeningpolish'></a>Phase 7 — Hardening / polish

- [ ] Confirm the combined-view page is **read-only** — it's a static HTML
      file with two `<img>` tags, so there's nothing on it that could send
      G-code, pause/cancel, or otherwise control either printer (out of
      scope, and also a good idea for a page with no login).
- [ ] Set the Pi to auto-update security patches
      (`sudo apt install unattended-upgrades`) since it's now internet-facing
      via the tunnel.
- [ ] Confirm all five services auto-start on boot and survive a full Pi
      power-cycle test:
      ```bash
      systemctl is-enabled ustreamer-a1.service go2rtc.service printer-page.service cloudflared
      ```
      (Bambu Connect's two instances were installed by OctoEverywhere's own
      installer, which sets up its own auto-start already — check those too
      with whatever service name(s) the installer reported during Phase 2.)
      Every line should print `enabled`; then do one more real `sudo reboot`
      and confirm `https://ariroth.com/printers/` comes back on its own with
      no manual intervention.
- [ ] Bookmark `https://ariroth.com/printers/` and confirm it works cleanly on
      mobile (Bambu Handy stays your control app; this is view-only).
- [ ] Optional: add a short "last updated" or auto-refresh indicator to the
      combined page so you can tell at a glance if a stream has silently
      stalled.

###  <a name='Phase8Tuneonceitslivedolaterwithrealtraffic'></a>Phase 8 — Tune once it's live (do later, with real traffic)

Nothing here blocks going live. Come back to it after the page has been
public for a while and you can see how the Pi behaves under real use.

- [ ] **Soak test with everything running** — both streams open, both Bambu
      Connect instances active, ideally mid-print (Bambu Connect's AI
      failure detection also uses CPU). Check:
      ```bash
      vcgencmd measure_temp
      vcgencmd get_throttled
      uptime
      ```
      Temperature under ~75°C, `throttled=0x0`, and load average under 4
      (the Pi 4 has 4 cores). Also watch ffmpeg in `top`: `%CPU` there is
      per core, so 100% is one core out of four.
- [ ] **Re-tune the P2S ffmpeg settings** in `/usr/local/etc/go2rtc.yaml` if
      the soak test shows heat, throttling, or stutter. Current line:
      `p2s: ffmpeg:p2s_raw#video=mjpeg#raw=-r 15 -vf scale=1080:-2`
      - `scale=1080:-2` means 1080 pixels *wide* (height follows the aspect
        ratio, so about 1080×608).
      - The P2S's feed, measured with `ffprobe`, is **1920×1080 at 30 fps**
        (about 62 million pixels/second). The current settings cut the
        scale + JPEG-encode work to about 10 million pixels/second (~16%).
      - Decoding the printer's H.264 feed always happens at the full
        1920×1080 at 30 fps, before `-r` and `scale` apply, so those
        settings can't reduce it. That's why ffmpeg stays around 90–100%
        even after lowering both. Further cuts to `-r` or width only trim
        the smaller remaining part.
      - Levers, easiest first: lower `-r` (15 → 10 → 5), then a smaller
        width (e.g. `scale=960:-2`).
      - Restart go2rtc after each change: `sudo systemctl restart go2rtc.service`.
- [ ] **Measure real bandwidth** once a few people are watching. MJPEG is
      bandwidth-hungry (roughly several Mbps per stream per viewer), and it
      multiplies by viewer count. With a 2 Gbps upload the internet link
      isn't the limit. Check instead:
      - Is the Pi on **wired gigabit Ethernet**? Wi-Fi may not sustain
        multiple viewers.
      - Does `cloudflared` CPU (visible in `top`) climb with viewer count?
        It encrypts every byte leaving the Pi.
- [ ] **Check Cloudflare's terms for video.** Cloudflare's self-serve terms
      have historically restricted serving large amounts of non-HTML content
      (video) through their proxy. Tunnels are treated differently from the
      CDN, but read their current terms and be ready to switch approaches
      (e.g. lower bitrate, or snapshot refresh instead of continuous video)
      if they object to sustained heavy traffic.
- [ ] **Decide how many viewers you're willing to support.** go2rtc shares one
      ffmpeg between all viewers of the P2S, but ustreamer (A1) and the
      printers themselves serve each viewer separately, and Bambu printers
      handle only a few concurrent local video connections. If traffic
      grows, consider an intermediate cache or a viewer limit.
- [ ] **Lock the A1 webcam's focus** (the C920 hunts in and out of focus
      while the bed moves, especially during calibration). Use your
      `/dev/v4l/by-id/...-video-index0` path from Phase 3 in the commands
      below.
      - See the focus controls:
        ```bash
        v4l2-ctl -d /dev/v4l/by-id/<your-c920>-video-index0 --list-ctrls | grep -i focus
        ```
        You should see `focus_automatic_continuous` and `focus_absolute`
        (range about 0–250).
      - Turn autofocus off, *then* set a fixed focus. The order matters:
        with autofocus still on, the manual value is ignored.
        ```bash
        v4l2-ctl -d /dev/v4l/by-id/<your-c920>-video-index0 --set-ctrl=focus_automatic_continuous=0
        v4l2-ctl -d /dev/v4l/by-id/<your-c920>-video-index0 --set-ctrl=focus_absolute=30
        ```
        You can run these while ustreamer is streaming. Keep the stream
        open in a browser and adjust the number until the build plate is
        sharp. Higher values focus closer, lower values farther; values
        move in steps of 5. `30` is only a starting guess.
      - To make it stick across restarts, add these two lines to the
        `[Service]` section of `ustreamer-a1.service`, above `ExecStart`,
        then run `sudo systemctl daemon-reload && sudo systemctl restart ustreamer-a1.service`:
        ```ini
        ExecStartPre=/usr/bin/v4l2-ctl -d /dev/v4l/by-id/<your-c920>-video-index0 --set-ctrl=focus_automatic_continuous=0
        ExecStartPre=/usr/bin/v4l2-ctl -d /dev/v4l/by-id/<your-c920>-video-index0 --set-ctrl=focus_absolute=30
        ```
      - Unverified: whether the C920 keeps these settings every time
        ustreamer reopens the device. If autofocus comes back after a
        restart or reboot, apply the setting after ustreamer starts instead
        (for example with `ExecStartPost=`).
      - Manual exposure and white balance are set the same way
        (`--list-ctrls` shows the control names) if brightness shifts while
        the bed moves.
- [ ] **Optional: stop video when nobody is looking.** Have the page load the
      streams only while the browser tab is visible (JavaScript
      `document.visibilityState`), so background tabs don't keep ffmpeg and
      the bandwidth running.
- [ ] Note the final tuned values here for future reference:
      P2S `-r` ___ / width ___; peak Pi temp ___; typical viewer count ___.

---

##  <a name='Referencelinks'></a>Reference links

- [Bambu Connect Raspberry Pi setup](https://blog.octoeverywhere.com/setup-bambu-connect-for-bambu-lab-3d-printers-on-a-raspberry-pi/)
- [Bambu Connect Docker/Docker Compose setup](https://blog.octoeverywhere.com/setup-bambu-connect-with-docker-or-docker-compose/) (alternative to the Pi, using your Docker machine instead, if you'd rather not maintain a second physical device)
- [External/Alternative webcam setup](https://help.octoeverywhere.com/knowledge-base/bambu-lab-3-d-printers/external-alternative-webcam-setup)
- [go2rtc](https://github.com/AlexxIT/go2rtc) — the local camera relay used in Phase 5 for the P2S
- [bambu-go2rtc](https://github.com/synman/bambu-go2rtc) — a purpose-built wrapper around go2rtc specifically for Bambu printers, worth a look if you outgrow the plain config in Phase 5 (e.g. wanting the P2S's serial-based access instead of the access-code URL)
- [bambulabs_api](https://bambutools.github.io/bambulabs_api/) — the Python library used in Phase 6 part B for progress/layer/ETA, talking to each printer's local status feed
- [OctoEverywhere API docs](https://docs.octoeverywhere.com/) — no longer needed by this plan, kept only as a pointer in case you want cloud-side data later
- [OctoEverywhere Live Links](https://octoeverywhere.com/live) — the simpler no-login public link option, one printer per link, not used in this plan's default path
- [OePi — purpose-built Pi image for Bambu Connect/Klipper Companion](https://github.com/OctoEverywhere/OePi) (worth a look for Phase 1–2 as a possible shortcut over a bare Raspberry Pi OS install)
- [Cloudflare Tunnel configuration file reference](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/)
