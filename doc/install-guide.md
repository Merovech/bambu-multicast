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
  - [That's it!](#thats-it)
  - [Help/Contact](#helpcontact)
  - [A Note on AI](#a-note-on-ai)
  - [Changelog](#changelog)
  - [Reference links](#reference-links)
</details>

Bambu Multicast (BM) is a companion for Bambu Lab 3D printers that lets you show multiple live streams of your printers on one web site.  This project began when I got tired of needing two copes of Bambu Studio open in order to monitor jobs on both of my printers simultaneously.

Multicast is largely intended for people who want to view this on a website without having a lot of technical knowledge.  The code is designed to require minimal changes -- if any -- and can be deployed and configured without any knowledge of CSS, HTML, JavaScript, or Python.

In fact, you can go through this guide and deploy without ever opening any file other than a few configs, and we will walk you through that.

> [!IMPORTANT] 
> This document covers installing BM on a Raspberry Pi, and all commands assume the bash shell.  However, any Linux-based machine will do.  Windows is currently not supported, though it may be in the future.
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
* (For external webcams) A webcam ([Amazon](https://www.amazon.com/Logitech-C920x-Pro-HD-Webcam/dp/B085TFF7M1/))
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
3. Write down or otherwise record each printer's **Serial Number**, **Access Code**, and **IP Address**.  You will need these later. 
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

The percentage, layer count, and remaining time all come from each printer's local status feed — a second connection (separate from the camera), using the same LAN access code, that Bambu printers expose for exactly this purpose. A small Python library (`bambulabs_api`) handles the details of that connection; you just call a few methods on it.

> [!IMPORTANT]
> If you already have the site set up, back up your files first, in case you don't like the changes an update brings.
> 
1. Download the latest release from github (TODO: LINK)
2. Unzip the files to a location of your choice
3. Copy `config/config.example.json` to `config.json` in the same location
      ```bash
      cp ./config/config.example.json ./config/config.json
      ```
4. Modify `config/config.json` using `nano ./config/config.json`.  See the table below for the description fields and the changes needed for each.
   | Field | Description |
   | - | - |
   | `web_server_port` | The port the sit will sit on. Change only if desired; the default is fine. |
   | `poll_interval_ms` | How frequently the web page will update itself from the server.  This is in ms, so 5000 = 5 seconds.  Change to taste. |
   | `printers` | The printers that will be streamed.  One entry per printer.  Add or remove as necessary. |
   | `label` | A label for the printer, which will be displayed on the page.  Update as needed. |
   | `camera_url` | The URL to the printer's camera that you set up earlier in this document. |
   | `ip` | The printer's IP address.  Note that this s **not** the address of the server streaming the cameras, it is the printer itself. |
   | `access_code` | The access code for the printer that you wrote down at the beginning of this process. |
   | `serial` | The serial number of the printer that you wrote down earlier in this process. |

5. Make `setup.sh` in the root of the site folder executable and run it.
   ```
   chmod +x setup.sh
   ./setup.sh
   ```

   This will set up a virtual environment, run it, and install the bambulabs_api prerequisite.  Your prompt will now show `(venv)` before it.  You can type `deactivate` to exit the virtual environment, and `source venv/bin/activate` to come back.  However, you must be in the virtual environment when you run this manually.



6. Test it by hand.  You must be in the virtual environment when you do this (see previous step).
   ```bash
   python3 server/server.py
   ```
   From another machine, reload `http://<pi-ip>:8090/` — the "Loading…" text should  show either a live percent/layer/ETA line if a print is running or "Idle" if not. You can also check the raw data directly: `curl http://localhost:8090/status.json` should print JSON for both printers. `Ctrl+C` to stop once confirmed.

####  <a name='C.Turnitintoonesystemdservice'></a>C. Turn it into one systemd service

1. Create a file at `/etc/systemd/sudo/printer-page.service`
   ```
   sudo touch /etc/systemd/system/printer-page.service
   ```

2. Using nano (`sudo nano /etc/systemd/system/printer-page.service`), copy the text below into the file, then press CTRL+S to save and CTRL+Q to exit.
   ```ini
   [Unit]
   Description=Combined printer camera + status page
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/home/pi/printer-page
   ExecStart=/home/pi/printer-page/venv/bin/python3 /home/pi/printer-page/server/server.py
   Restart=always
   RestartSec=2
   User=pi

   [Install]
   WantedBy=multi-user.target
   ```
   Replace `/home/pi/printer-page` (it appears twice) with the real path if your username isn't `pi` — run `pwd` inside that folder to confirm.  Also change `printer-page` to whatever folder you unzipped the code into.

   Using the venv's own `python3` binary is what makes `import bambulabs_api` work without needing that package installed system-wide.

3. Load, start, and verify it.
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now printer-page.service
   systemctl status printer-page.service
   journalctl -u printer-page.service -f
   ```
   Watch the logs for a moment for any Python errors (a typo'd IP/access code/serial would show up here as a connection error from one of the background threads).

   > [!NOTE]
   > You probably will see some errors if everything goes well, specifically these two:
   > * Printer Values Not Available Yet
   > * Not connected to the MQTT server
   >
   > These are fine.  They come from the printers and they're noise.  You can safely ignore them.

4. Prove restart-on-failure
   ```bash
   systemctl status printer-page.service # Note the PID it displays
   sudo systemctl kill -s SIGKILL printer-page.service
   systemctl status printer-page.service
   ```
   
   You should see a different PID for the second call to `systemctl`.

5. Prove restart-on-reboot
   ```
   sudo reboot
   ```

   Wait a minute or two for the reboot, then reload `http://<pi-ip>:8090/`

6. Enjoy!

## That's it!
You're done!  You now should have a working site that streams your printers onto one page.  What you do with it from here is up to you.  Enjoy!

## Help/Contact
If you run into any problems, please feel free to contact me on github (Merovech) or Reddit (u/pyran).  If you find bugs or have suggestions for new features, please consider filing an issue on Github.

## A Note on AI
This project was designed, and developed with the assistance of Claude.  It was tested extensively, modified, cleaned up, and in many parts rewritten by me.  I have been a software developer for over 25 years, and I heavily supervised Claude's output for safety, cleanliness, and functionality.

In other words, Claude saved me research time and coding time, but I reviewed the code before I was willing to trust it.

I've also been running it both locally and on a domain for quite a while before I even thought of packaging it up and releasing it, and it's working great so far.

## Changelog
| Date | Change |
| - | - |
| 29 Sep 2026 | Initial draft completed. |

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
