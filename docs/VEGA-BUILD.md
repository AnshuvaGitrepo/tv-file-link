# Build and test the Vega OS edition

Status: source ready (v1.4.0). TypeScript type check and the JavaScript bundle pass on Windows. The VPKG and the device test are **pending**: they need the steps below.

## 1. Host

Amazon supports only these build hosts (Windows and WSL are not supported):

- Ubuntu 20.04 or newer, x86_64, or
- macOS (Apple silicon; Intel Macs only up to SDK 0.24)
- About 20 GB free disk space

## 2. Tools

1. Install the Vega SDK and CLI: https://developer.amazon.com/docs/vega/0.23/install-vega-sdk.html (pick the SDK version that matches your Stick's Vega OS).
2. Node.js 22.14 or newer, a C++ toolchain (Xcode command line tools / build-essential), Watchman.
3. Activate the SDK environment in the terminal (as described on the install page).

## 3. Build

Copy both `vega-os` and `shared` from this project to the host (keep them side by side), then:

```bash
cd vega-os
npm ci
npm run build        # runs build.sh: browser page header, native module, vega package
```

The VPKG appears under `vega-os/build/`. Pick the one whose architecture matches the Stick and copy it back into this project's `vega-os` folder.

Build guide: https://developer.amazon.com/docs/vega/0.24/build-an-app.html

## 4. Install and run on the Stick

Enable developer mode on the Vega Stick, register it with the Vega CLI, then install and launch the VPKG as described in https://developer.amazon.com/docs/vega/0.24/run-apps.html

## 5. Device checks (record results in docs/TESTING.md)

1. App opens, AS logo, focus on Start transfer.
2. Start transfer: address + six-digit code shown.
3. **Incoming connection:** on a phone on the same Wi-Fi, open the address. If the page loads, enter the code and upload and download a file (compare checksums). This is the key unknown on Vega.
4. File manager (My files): New folder, Copy + Paste, Move here, Rename, Delete a folder with contents (warning shows the item count), Details, Sort, image viewer, text viewer.
5. Stop transfer and Home: the address stops answering.

## If incoming connections are blocked

The app's local web server cannot work then. The smallest alternative is a relay: the TV app and the browser both connect out to a small relay server that checks the code and passes the files. That needs internet access (or a computer on the network running the relay), and files no longer travel directly between the two devices.
