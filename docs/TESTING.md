# Testing

All automated tests ran on the Windows build PC with Android TV emulators (x86, 1920x1080 @ 320 dpi).
Android 11 matches Fire OS 8; Android 9 matches Fire OS 7. **No physical Fire TV or Vega device was available**;
see *Pending* below.

## How to run

```powershell
# Start an emulator (AVD TVFileLink_TV30 = Android 11, TVFileLink_TV28 = Android 9)
& "$env:ANDROID_HOME\emulator\emulator.exe" -avd TVFileLink_TV30 -no-window -no-audio -no-snapshot -gpu swiftshader_indirect
cd work\tests
$env:OLD_APK = "<v1.2 APK with x86 code>"   # for the upgrade check (the shipped v1.2 has no x86 code)
python emulator_test.py        # Wi-Fi transfer: 38 checks
python filemanager_test.py     # file manager
python make_testing_md.py      # rebuild this file
```

How the tests work: the TV app is driven only with D-pad key events (`adb shell input keyevent`), and the screen
is read with uiautomator. The browser side uses the same HTTP requests as the browser page, through an adb port
forward and an on-device relay (the emulator gives the app the Wi-Fi address 10.0.2.16). Files are compared by
SHA-256. While video is drawing, uiautomator cannot read the screen, so playback is checked in Android's
`dumpsys audio` (player state) and `dumpsys media.player` (video session).

## Summary

Final run on the release APK (16 November 2026). Note: the first attempt of the Android 9 file manager suite
lost the screen reader soon after the emulator booted (7 checks passed, then 12 failed because the test left
the app). The rerun on the same emulator and APK passed all checks; its results are below.

| Suite | Emulator | Passed | Failed | Pending | Date |
|---|---|---|---|---|---|
| Wi-Fi transfer | Android 11 (API 30) | 38 | 0 | 0 | 2026-11-16 11:38 |
| Wi-Fi transfer | Android 9 (API 28) | 38 | 0 | 0 | 2026-11-16 11:53 |
| File manager | Android 11 (API 30) | 26 | 0 | 0 | 2026-11-16 11:38 |
| File manager | Android 9 (API 28) | 27 | 0 | 0 | 2026-11-16 12:34 |

## Wi-Fi transfer: Android 11 (API 30)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | v1.2 baseline: upload a file with the old release | PASS | connect 200, upload 201 |
| 2 | Update installs over v1.2 (same app ID and signing key) | PASS | Success; versionName=1.4 (expected 1.4) |
| 3 | v1.2 file still listed after the update | PASS | My files shows: kept-from-v1.2.txt |
| 4 | App opens with remote focus on Start transfer | PASS | focused: Start transfer |
| 5 | D-pad reaches transfer and file controls | PASS | Refresh: 3 key presses; New folder: 2 key presses; Start transfer: 1 key presses |
| 6 | Create folder 'Photos' on the TV | PASS | Save pressed via dpad |
| 7 | Start transfer shows address and six-digit code | PASS | address http://10.0.2.16:42833, code 641980 |
| 8 | Browser page loads from the TV address | PASS | HTTP 200, 215196 bytes |
| 9 | File list refused without connecting | PASS | HTTP 403 |
| 10 | Correct code connects | PASS | HTTP 200 |
| 11 | Upload 'Holiday video.bin' (6,291,579 bytes) to Photos | PASS | HTTP 201 |
| 12 | Upload 'Travel itinerary.txt' (6,600 bytes) to My files | PASS | HTTP 201 |
| 13 | Upload 'notes 0123.txt' (24 bytes) to My files | PASS | HTTP 201 |
| 14 | Uploaded files appear in the right folders | PASS | root: ['Photos', 'Travel itinerary.txt', 'kept-from-v1.2.txt', 'notes 0123.txt']; Photos: ['Holiday video.bin'] |
| 15 | Download 'Holiday video.bin' and compare SHA-256 | PASS | sent 6c84653178c85f2c..., received 6c84653178c85f2c... |
| 16 | Download 'Travel itinerary.txt' and compare SHA-256 | PASS | sent 8c96d49814fbe7c2..., received 8c96d49814fbe7c2... |
| 17 | Download 'notes 0123.txt' and compare SHA-256 | PASS | sent c2487bb1681706f8..., received c2487bb1681706f8... |
| 18 | Download the file stored by v1.2 | PASS | HTTP 200, match=True |
| 19 | Duplicate name is refused with a clear message | PASS | HTTP 409: "Travel itinerary.txt" already exists in this folder. Rename the file and upload it again. |
| 20 | Path outside the library is refused | PASS | HTTP 400: Invalid path. |
| 21 | Download with a made-up key is refused | PASS | HTTP 403 |
| 22 | Upload over the 2 GiB limit is refused | PASS | HTTP 400 |
| 23 | Upload to a folder that no longer exists is refused | PASS | HTTP 404: Destination folder unavailable. |
| 24 | Real browser connects and shows the file list (Chrome) | PASS | {"inputmode": "numeric", "inputType": "text", "autocomplete": "one-time-code", "connectedStatus": "Connected to your TV.", "rows": ["Photos / Folder", "Travel i |
| 25 | Code box asks phones for the numeric keypad | PASS | inputmode=numeric, type=text |
| 26 | TV list shows browser uploads without pressing Refresh | PASS | names: Photos, kept-from-v1.2.txt, notes 0123.txt, Travel itinerary.txt |
| 27 | Rename a file on the TV | PASS | menu reached=True; now: ['Photos', 'kept-from-v1.2.txt', 'renamed-notes.txt', 'Travel itinerary.txt'] |
| 28 | Deleting a folder with files warns with the item count, then deletes it | PASS | via dpad; warning: The folder and the 1 item inside it will be deleted. This cannot be undone. |
| 29 | Delete a file after confirmation | PASS | via dpad |
| 30 | Delete an empty folder after confirmation | PASS | via dpad |
| 31 | Stop transfer closes the server | PASS | connection refused after Stop |
| 32 | Wrong code is refused | PASS | HTTP 403: That code is not correct. Enter the six-digit code shown on your TV. |
| 33 | After 3 wrong codes, even the right code must wait | PASS | HTTP 429: Too many wrong codes. Wait 1 second and try again. |
| 34 | Right code works after the short wait | PASS | HTTP 200 |
| 35 | Key from the previous session is refused | PASS | HTTP 403 |
| 36 | Code with a leading zero is shown in full and accepted | PASS | code 007535 after 3 restarts, HTTP 200 |
| 37 | Leaving the app (Home) closes the server | PASS | connection refused after Home |
| 38 | Reopened app shows Start transfer (no session) | PASS |  |

## Wi-Fi transfer: Android 9 (API 28)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | v1.2 baseline: upload a file with the old release | PASS | connect 200, upload 201 |
| 2 | Update installs over v1.2 (same app ID and signing key) | PASS | Success; versionName=1.4 (expected 1.4) |
| 3 | v1.2 file still listed after the update | PASS | My files shows: kept-from-v1.2.txt |
| 4 | App opens with remote focus on Start transfer | PASS | focused: Start transfer |
| 5 | D-pad reaches transfer and file controls | PASS | Refresh: 3 key presses; New folder: 2 key presses; Start transfer: 1 key presses |
| 6 | Create folder 'Photos' on the TV | PASS | Save pressed via tap |
| 7 | Start transfer shows address and six-digit code | PASS | address http://192.168.232.2:42838, code 110988 |
| 8 | Browser page loads from the TV address | PASS | HTTP 200, 215196 bytes |
| 9 | File list refused without connecting | PASS | HTTP 403 |
| 10 | Correct code connects | PASS | HTTP 200 |
| 11 | Upload 'Holiday video.bin' (6,291,579 bytes) to Photos | PASS | HTTP 201 |
| 12 | Upload 'Travel itinerary.txt' (6,600 bytes) to My files | PASS | HTTP 201 |
| 13 | Upload 'notes 0123.txt' (24 bytes) to My files | PASS | HTTP 201 |
| 14 | Uploaded files appear in the right folders | PASS | root: ['Photos', 'Travel itinerary.txt', 'kept-from-v1.2.txt', 'notes 0123.txt']; Photos: ['Holiday video.bin'] |
| 15 | Download 'Holiday video.bin' and compare SHA-256 | PASS | sent f5b3b6e8eeef4993..., received f5b3b6e8eeef4993... |
| 16 | Download 'Travel itinerary.txt' and compare SHA-256 | PASS | sent 8c96d49814fbe7c2..., received 8c96d49814fbe7c2... |
| 17 | Download 'notes 0123.txt' and compare SHA-256 | PASS | sent c2487bb1681706f8..., received c2487bb1681706f8... |
| 18 | Download the file stored by v1.2 | PASS | HTTP 200, match=True |
| 19 | Duplicate name is refused with a clear message | PASS | HTTP 409: "Travel itinerary.txt" already exists in this folder. Rename the file and upload it again. |
| 20 | Path outside the library is refused | PASS | HTTP 400: Invalid path. |
| 21 | Download with a made-up key is refused | PASS | HTTP 403 |
| 22 | Upload over the 2 GiB limit is refused | PASS | HTTP 400 |
| 23 | Upload to a folder that no longer exists is refused | PASS | HTTP 404: Destination folder unavailable. |
| 24 | Real browser connects and shows the file list (Chrome) | PASS | {"inputmode": "numeric", "inputType": "text", "autocomplete": "one-time-code", "connectedStatus": "Connected to your TV.", "rows": ["Photos / Folder", "Travel i |
| 25 | Code box asks phones for the numeric keypad | PASS | inputmode=numeric, type=text |
| 26 | TV list shows browser uploads without pressing Refresh | PASS | names: Photos, kept-from-v1.2.txt, notes 0123.txt, Travel itinerary.txt |
| 27 | Rename a file on the TV | PASS | menu reached=True; now: ['Photos', 'kept-from-v1.2.txt', 'renamed-notes.txt', 'Travel itinerary.txt'] |
| 28 | Deleting a folder with files warns with the item count, then deletes it | PASS | via dpad; warning: The folder and the 1 item inside it will be deleted. This cannot be undone. |
| 29 | Delete a file after confirmation | PASS | via dpad |
| 30 | Delete an empty folder after confirmation | PASS | via dpad |
| 31 | Stop transfer closes the server | PASS | connection refused after Stop |
| 32 | Wrong code is refused | PASS | HTTP 403: That code is not correct. Enter the six-digit code shown on your TV. |
| 33 | After 3 wrong codes, even the right code must wait | PASS | HTTP 429: Too many wrong codes. Wait 1 second and try again. |
| 34 | Right code works after the short wait | PASS | HTTP 200 |
| 35 | Key from the previous session is refused | PASS | HTTP 403 |
| 36 | Code with a leading zero is shown in full and accepted | PASS | code 049769 after 9 restarts, HTTP 200 |
| 37 | Leaving the app (Home) closes the server | PASS | connection refused after Home |
| 38 | Reopened app shows Start transfer (no session) | PASS |  |

## File manager: Android 11 (API 30)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | Install v1.4 | PASS | Success |
| 2 | Test files in shared storage (images, text, WAV, MP4 from screenrecord, nested folder) | PASS | Holiday , clip.mp4 , notes.txt , photo1.png , photo2.png , song.wav; clip.mp4 28427 bytes |
| 3 | Location tabs shown | PASS | My files, Internal storage |
| 4 | Internal storage asks for access first | PASS | Allow storage access button shown |
| 5 | Allow opens the All files access screen (Android 11) | PASS | com.android.tv.settings/.device.apps.AppManagementActivity |
| 6 | After access is granted the hint is replaced by 'Storage access is on.' | PASS | ['Storage access is on.'] |
| 7 | Internal storage lists folders after access | PASS | Alarms, Android, Audiobooks, DCIM, Documents, Download, Movies, Music, Notifications, Pictures, Podcasts, Ringtones |
| 8 | Open Download / TVFL-Test with the D-pad | PASS | Holiday, clip.mp4, notes.txt, photo1.png, photo2.png, song.wav |
| 9 | Image viewer opens (1 of 2) | PASS | photo1.png (1 of 2) Left / Right: previous / next Back: close |
| 10 | Right on the remote shows the next image | PASS | photo2.png (2 of 2) Left / Right: previous / next Back: close |
| 11 | Text viewer shows the file | PASS | TV File Link notes Line two: file manager test xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| 12 | Audio player plays, Select pauses and resumes | PASS | audio service: started -> paused -> started |
| 13 | Back closes the player and stops playback | PASS | audio service after Back: released |
| 14 | Video player opens and plays the MP4 (H.264) | PASS | media.player shows the app's video/avc session |
| 15 | Details shows type, size and date | PASS | photo1.png Type: image/png Size: 4.7 KB (4859 bytes) Modified: Nov 16, 2026 5:40 AM Location: Internal storage / Download/TVFL-Test OK |
| 16 | Sort by size puts the largest file first | PASS | order: song.wav, clip.mp4, photo2.png, photo1.png, notes.txt |
| 17 | Copy from internal storage, Paste into My files | PASS | button 'Paste: photo1.png'; My files: ['photo1.png'] |
| 18 | Move from internal storage into My files (original removed) | PASS | button 'Move here: notes.txt' pressed=True (focus before: Location My files); app: ['Moved notes.txt.']; source gone=True; My files: ['photo1.png', 'notes.txt'] |
| 19 | Copy to My files copies a folder with subfolders | PASS | Holiday, photo1.png, notes.txt |
| 20 | Copied files are in My files and download intact through Wi-Fi transfer | PASS | photo1.png SHA-256 match and Holiday/Day 1/beach.txt listed |
| 21 | Rename a file in internal storage | PASS | Holiday , beach.png , clip.mp4 , photo1.png , song.wav |
| 22 | Delete a folder with contents after a warning that counts its items | PASS | Delete folder Holiday? The folder and the 3 items inside it will be deleted. This cannot be undone. CANCEL DELETE |
| 23 | USB drive appears as a location and accepts a pasted file | PASS | disk disk:7,208; tabs: ['My files', 'Internal storage', 'Virtual SD card']; file on USB volume: True |
| 24 | Removing the drive while it is open returns to My files with a message | PASS | title 'My files'; message ['Virtual SD card is no longer available.']; tabs ['My files', 'Internal storage'] |
| 25 | Open with another app hands over the file or explains | PASS | top: com.anshuva.tvfilelink/.MainActivity; No app can open this file No app on this TV can open photo1.png. Install an app for this file type, |
| 26 | Location tabs switch when selected (retries are listed) | PASS | My files: switched on attempt 2 |

## File manager: Android 9 (API 28)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | Install v1.4 | PASS | Success |
| 2 | Test files in shared storage (images, text, WAV, MP4 from screenrecord, nested folder) | PASS | Holiday , clip.mp4 , notes.txt , photo1.png , photo2.png , song.wav; clip.mp4 28163 bytes |
| 3 | Location tabs shown | PASS | My files, Internal storage |
| 4 | Internal storage asks for access first | PASS | Allow storage access button shown |
| 5 | Allow shows the Storage permission prompt (Android 9) | PASS | Allow TV File Link to access photos, media, and files on your device? You can change this later in Settings > Apps Allow Deny |
| 6 | Storage permission granted with the remote | PASS |  |
| 7 | After access is granted the hint is replaced by 'Storage access is on.' | PASS | ['Storage access is on.'] |
| 8 | Internal storage lists folders after access | PASS | Alarms, Android, DCIM, Download, Movies, Music, Notifications, Pictures, Podcasts, Ringtones |
| 9 | Open Download / TVFL-Test with the D-pad | PASS | Holiday, clip.mp4, notes.txt, photo1.png, photo2.png, song.wav |
| 10 | Image viewer opens (1 of 2) | PASS | photo1.png (1 of 2) Left / Right: previous / next Back: close |
| 11 | Right on the remote shows the next image | PASS | photo2.png (2 of 2) Left / Right: previous / next Back: close |
| 12 | Text viewer shows the file | PASS | TV File Link notes Line two: file manager test xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx |
| 13 | Audio player plays, Select pauses and resumes | PASS | audio service: started -> paused -> started |
| 14 | Back closes the player and stops playback | PASS | audio service after Back: released |
| 15 | Video player opens and plays the MP4 (H.264) | PASS | media.player shows the app's video/avc session |
| 16 | Details shows type, size and date | PASS | photo1.png Type: image/png Size: 4.7 KB (4859 bytes) Modified: Nov 16, 2026 6:36 AM Location: Internal storage / Download/TVFL-Test OK |
| 17 | Sort by size puts the largest file first | PASS | order: song.wav, clip.mp4, photo2.png, photo1.png, notes.txt |
| 18 | Copy from internal storage, Paste into My files | PASS | button 'Paste: photo1.png'; My files: ['photo1.png'] |
| 19 | Move from internal storage into My files (original removed) | PASS | button 'Move here: notes.txt' pressed=True (focus before: Location My files); app: ['Moved notes.txt.']; source gone=True; My files: ['photo1.png', 'notes.txt'] |
| 20 | Copy to My files copies a folder with subfolders | PASS | Holiday, photo1.png, notes.txt |
| 21 | Copied files are in My files and download intact through Wi-Fi transfer | PASS | photo1.png SHA-256 match and Holiday/Day 1/beach.txt listed |
| 22 | Rename a file in internal storage | PASS | Holiday , beach.png , clip.mp4 , photo1.png , song.wav |
| 23 | Delete a folder with contents after a warning that counts its items | PASS | Delete folder Holiday? The folder and the 3 items inside it will be deleted. This cannot be undone. CANCEL DELETE |
| 24 | USB drive on Android 9 is shown read-only with an explanation (no Paste / New folder) | PASS | disk disk:7,0; tabs: ['My files', 'Internal storage', 'Virtual SD card']; note ['Read-only on this Fire TV: apps can open and copy files from Virtual SD card, b |
| 25 | Removing the drive while it is open returns to My files with a message | PASS | title 'My files'; message ['Virtual SD card is no longer available.']; tabs ['My files', 'Internal storage'] |
| 26 | Open with another app hands over the file or explains | PASS | top: com.anshuva.tvfilelink/.MainActivity; No app can open this file No app on this TV can open photo1.png. Install an app for this file type, |
| 27 | Location tabs switch when selected (retries are listed) | PASS | My files: switched on attempt 2 |

## Also verified on the build PC

- APK: v2 + v3 signature, certificate SHA-256 `237eabf4...d4ac8ccf` (same as v1.2), versionCode 5 / 1.4, zipalign, ARM 32/64-bit libraries.
- Vega: `npm run typecheck` and `react-native bundle --platform kepler` succeed; shared C++ compiles for ARM64.

## Pending (needs hardware)

| Test | What is needed |
|---|---|
| Fire OS on a physical Fire TV Stick (ARM): install, update, remote, transfer, file manager | Stick with ADB debugging, computer on the same network |
| Fire OS 8 All files access screen on a real Fire TV | Fire OS 8 device |
| Real USB drive (OTG) on a Stick | FAT32/exFAT drive + OTG adapter (the emulator used Android's virtual disk) |
| Writing to USB on Fire OS 6/7 | Storage Access Framework grant in the app (follow-up); read-only today, by design |
| Video formats on hardware (MKV, HEVC, 4K) | Sample files on the Stick (emulator: H.264 MP4 and WAV only) |
| Transfer between two separate devices; per-device key on two phones | Stick + two phones on home Wi-Fi |
| Number keypad on iPhone and Android phones | Real phones (Chrome check: `inputmode=numeric`) |
| Storage-full message | Nearly full Stick |
| Vega VPKG build + device test (incoming connections, library file manager) | Ubuntu/macOS + Vega SDK, Vega device (see VEGA-BUILD.md) |
| Large file (> 1 GB) on 32-bit ARM | cpp-httplib warns about 32-bit builds; the 32-bit x86 emulator passed |
