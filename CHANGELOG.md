# Changelog

## 1.4.1 (versionCode 6), 16 November 2026: new app icon

- New TV File Link logo (a TV with a folder, two-way arrows and a Wi-Fi badge) for the Fire TV home-screen tile, the app icon, the header in the app, the browser transfer page and the Vega app. It replaces the personal AS logo.
- No other changes. Signed with the same key, so it installs over 1.2, 1.3 and 1.4 and keeps My files.
- Retested on Android TV emulators: Android 9 (file manager 27/27, transfer 38/38) and Android 11 (26/26, 38/38).

## 1.4 (versionCode 5), 16 November 2026: file manager

Fire OS
- New file manager with locations: My files (app library), Internal storage, and each USB drive / SD card, with free space. Drive tabs appear and disappear live; if the open drive is removed, the app returns to My files with a message.
- USB drives are writable on Fire OS 8; on Fire OS 6/7 (Android 7-9 rule) they are shown read-only with an explanation, and Copy from them works.
- Copy, Move (across locations, including USB), Rename, New folder, Delete (folders with contents after a warning that counts the items), Details, Sort by name / date / size, Copy to My files.
- Built-in viewers: images (Left/Right: previous/next), video and audio player (Select: play/pause, Left/Right: -10 s / +10 s), text viewer (first 512 KB). Other files: Open with another app (read-only, one-time grant). Android TV placeholder handlers are ignored, so a clear message appears when no real app can open the file.
- Storage permission: Storage prompt on Fire OS 6/7; All files access on Fire OS 8, with fallbacks when the direct settings screen is missing. Without access, My files keeps working; once access is granted the hint changes to "Storage access is on."
- Remote: Menu key opens Options; Back goes up, then back to My files.
- Browser transfer unchanged: a connected device only sees My files.
- Tested on Android TV emulators: Android 9 (file manager 27/27, transfer 38/38) and Android 11 (26/26, 38/38). Installs over 1.2 and 1.3 with the same key.

Vega OS (source)
- Library-only file manager (Vega gives apps no shared storage): Copy / Move / Paste, Delete folders with contents, Details, Sort, image and text viewer. Video/audio playback not available yet.
- Shared C++: new actions copy, move, rmtree, stat, read; list now includes the modified time.

## 1.3 (versionCode 4), 16 November 2026

- Numeric keypad for the code on phones; per-device session keys tied to the browser's address.
- Wrong-code back-off (1, 2, 4 ... 60 s after 3 in a row), 10 per minute per device, 30 per minute overall, 8 devices per session.
- Browser: icons, Download buttons, overall upload progress, clearer messages.
- TV: larger address and code; list refreshes itself while a transfer is active.
- APK also contains x86 code for Android TV emulators.

## 1.2 (versionCode 3)

- First signed sideload release (Fire OS) and Vega OS source.
