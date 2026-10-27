# Bambu Multicast

[![License: MIT](https://img.shields.io/github/license/Merovech/bambu-multicast)](LICENSE) [![Latest release](https://img.shields.io/github/v/release/Merovech/bambu-multicast?include_prereleases&sort=semver&label=version)](https://github.com/Merovech/bambu-multicast/releases) 
[![Latest install guide update](https://img.shields.io/github/last-commit/Merovech/bambu-multicast?path=doc%2Finstall-guide.pdf&label=Install%20Guide%20PDF%20Updated)](doc/install-guide.pdf) [![Unit tests](https://github.com/Merovech/bambu-multicast/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/Merovech/bambu-multicast/actions/workflows/tests.yml)

Bambu Multicast puts the live camera views and the current status of all your Bambu Lab 3D printers on one web page.  No more keeping a separate copy of Bambu Studio or a separate web pages open for every printer just to see how each print is going; now you can see the print in real-time along with a Bambu Studio-like block of information about layers, time estimates, etc.

It is made for people who run one or more Bambu Lab printers and want a simple "everything at a glance" page, for themselves or to share with friends and family, **without needing a lot of technical knowledge**.  You can set it up from the install guide and a single settings file, without ever opening a line of code.  If you *do* want to tinker, the code is small, tested, and easy to change.

The page is view-only: it shows what your printers are doing but cannot control them, and it has no logins or accounts.  It was designed as a monitoring tool, not  a full controller for your printers.  It has undergone security reviews, code reviews, and all the checks I can think of to make it as safe as possible to use; it's safe enough that you can put it on a public website and rest assured no one will touch your prints!

This project was developed because I wanted it and thought it was nifty enough that others might want it too.  I use it every day, hosted on my local network..

> [!NOTE]
> I am not affiliated with Bambu Labs in any way; I just own two of their printers.  They have neither endorsed nor contributed to it, and they're probably finding out about it at the same time you are.

## How it works

Think of it as three small helpers working together on one little computer:

1. **A camera helper** takes the video from each printer's camera (or from a webcam pointed at the printer) and makes it available on your home network.
2. **A status helper** quietly asks each printer, every few seconds, what it is up to: printing, paused, idle, finished, or in trouble, etc..
3. **A web page** combines the two.  Anyone who opens it sees one panel per printer, with the live video above the printer's current state.

Everything runs on your own equipment, and your printers are never controlled from the page.

## Requirements

- One or more **Bambu Lab printers**, with LAN Mode turned on.
- A **camera** for each printer: the printer's built-in camera, or a USB webcam.
- A small **computer to host the site on**, plus a way to put an operating system on it.  A Raspberry Pi 4B or newer with a 32 GB microSD card works well.
- A free [OctoEverywhere](https://octoeverywhere.com/) account (used to get the built-in camera feed).

> [!NOTE]
> This was written specifically to be hosted on a **Raspberry Pi running Linux**, and the install guide assumes exactly that.  Other Linux computers should work but have not been tested.  Windows is not supported, though it would probably work with some command changes.

## Getting started

Follow the **[install guide](doc/install-guide.md)** (also available as a [PDF](doc/install-guide.pdf)).  It walks you through everything, from setting up your printers and the Pi, to getting the cameras onto your network, to installing the site and adding your printers to a single settings file.

A major goal of this project was to allow non-technical people to set it up as easily as possible.  Technical shell commands are going to be required, but the guide will walk you through this with as little pain as possible, and it was tested by simply following it myself.  You will need to make a few changes to your config settings for your specific printers and addresses, but many of the settings can be left alone and you need no prior knowledge of HTML, Javascript, or Python.

In other words, if you follow the guide, you can have no idea what the code actually does or how to read it, and it will still work.

The packaged site, ready to install, will be published on the [Releases page](https://github.com/Merovech/bambu-multicast/releases); there is no release yet.

## Contributing

Contributions are welcome, whether that is a bug fix, a new feature, or better documentation.

1. [Fork the repository](https://github.com/Merovech/bambu-multicast/fork) on GitHub and clone your fork.
2. Set up a development copy with one command: `bash scripts/setup-dev.sh`.  It creates the Python environment, installs everything the site and its tests need, and copies the example settings file to `config/config.json`.
3. Create a branch for your change, and make it.
4. Run the tests before you submit: `python -m pytest` for the server and `npm test` for the web page.
5. Push your branch and open a pull request against `main`, describing what you changed and why.

The tests also run automatically on every pull request and again on every merge to `main`, and a change is only merged when they all pass.

## Questions, bugs, and feedback

- For **bugs** or questions about **the project itself**, please [open an issue](https://github.com/Merovech/bambu-multicast/issues) on GitHub.
- For anything else, send me a message on GitHub ([@Merovech](https://github.com/Merovech)) or on Reddit ([u/pyran](https://www.reddit.com/user/pyran)).


## AI Disclosure
This project was made by me using Anthropic's Claude over the course of about a month.  I am a 26-year veteran of the software industry who has had roles in testing, development, architecture, and management; Claude is an LLM.

Claude's Role:
* Author code and tests
* Search the internet for solutions to issues
  

My Role:
* Create the concept, design, and goals for the project
* Review all code
* Ensure proper tests are being created, run, and passing
* Ensure proper reviews (security, style, legal) have been done and pass
* Test the final result and ensure bugs are fixed

In other words, this wasn't handed to an LLM and the result thrown out the world; this was carefully designed, tested, and reviewed by a professional human.

## License

Bambu Multicast is released under the [MIT License](LICENSE): you may use, change, and share it, provided that the copyright notice stays with it.  Some data is derived from other open-source projects; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Changelog

| Date        | Change           |
| ----------- | ---------------- |
| 26 Oct 2026 | Initial version. |
