# File manager (since v1.4)

## Locations

| Location | Fire OS | Vega OS |
|---|---|---|
| My files (app library; the only folder the browser transfer can see) | YES | YES |
| Internal storage (Download, Movies, Pictures ...) | YES, after storage access | NO: Vega apps only see `/data` and `/tmp` |
| USB drive / SD card | Fire OS 8: read and write (All files access). Fire OS 6/7: **read-only** (open, copy from) | NO (no documented API) |

**USB on Fire OS 6/7.** Android 7-9 let apps read removable drives but not write to them without the Storage Access Framework (a folder picker grant). The app probes each drive (creates and deletes a hidden `.tvlink-probe` file). If that fails, the tab shows "Read-only on this Fire TV ...", and New folder, Paste, Move, Rename and Delete are not offered there. Copy (to My files or Internal storage) still works. Writing to USB on Fire OS 6/7 would need a Storage Access Framework grant: a possible follow-up. The same change would also matter for Google Play, which restricts All files access (see [PUBLISHING.md](PUBLISHING.md)).

Fire OS finds removable volumes with `Context.getExternalFilesDirs(null)` (index 1 and up) and labels them with `StorageVolume.getDescription()`. The app listens for drives being mounted and removed (ACTION_MEDIA_MOUNTED / UNMOUNTED / REMOVED / EJECT / BAD_REMOVAL) while it is open, and also rebuilds the list on every return to the app and on Refresh. If the open drive disappears, the app returns to My files with "<drive> is no longer available."

## Permissions (Fire OS)

| Fire OS | Android | How access is granted |
|---|---|---|
| 6 | 7.1 (API 25) | Storage permission prompt (READ/WRITE_EXTERNAL_STORAGE) |
| 7 | 9 (API 28) | Storage permission prompt |
| 8 | 10 (API 29) | Storage permission prompt (`requestLegacyExternalStorage`), or All files |
| 8 | 11 (API 30) | All files access (`MANAGE_EXTERNAL_STORAGE`) |

(On the Android 11 TV emulator the direct screen is missing; the app fell back to the app settings page, as designed.) On Android 11 the app tries, in order: `ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION` (direct screen), `ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION` (list screen), `ACTION_APPLICATION_DETAILS_SETTINGS` (app settings; Permissions > Storage > All files). Some TV builds lack the direct screen. If nothing opens, the app shows the Settings path in words. Without access, the storage tabs show an "Allow storage access" button, and My files keeps working. When access is granted, the how-to hint is replaced by "Storage access is on."

Opening Settings leaves the app, so an active Wi-Fi transfer stops, as it does whenever the app goes to the background.

## Operations

| Operation | Notes |
|---|---|
| Copy / Move | Pick Copy or Move in Options, open the destination (any location or folder), select Paste / Move here. Name clash: `name (1).ext`. Move on the same drive is an instant rename; across drives it is copy + delete. Progress dialog with Cancel: a cancelled copy is removed; a cancelled move leaves the original. Free space is checked first. A folder cannot be copied into itself. |
| Delete | Files: confirm. Folders: confirm with the number of items inside; then recursive delete. |
| Rename / New folder | Names cannot contain `/` or `\`, control characters, or start with `.tvlink-` (transfer staging). |
| Details | Type (MIME), size (folders: total size and item count, computed in the background), modified time, location. |
| Sort | Name, Date (newest first), Size (largest first); folders always first. |
| Hidden items | Names starting with `.` and symbolic links are not listed, and links are not followed while copying or deleting. |

## Viewers (Fire OS)

Viewers are full-screen dialogs inside the app, so an active transfer keeps running.

- Images: decoded down to screen size (keeps memory low on the Stick). Left/Right: previous/next image in the folder.
- Video and audio: Android `VideoView` / MediaPlayer. Select: play/pause, Left/Right: -10 s / +10 s, Back: close (playback stops). A format the TV cannot decode shows a message pointing to Open with another app.
- Text: first 512 KB as UTF-8.
- Open with another app: `ACTION_VIEW` with a `content://com.anshuva.tvfilelink.files/...` URI from the app's private, non-exported provider, with a one-time read grant. If no app handles the type, a message explains the alternatives.

## Tested

`work/tests/filemanager_test.py` on Android TV emulators: Android 9 (API 28) 27 of 27, Android 11 (API 30) 26 of 26. The USB drive was emulated with Android's virtual disk (`sm set-virtual-disk true`): on Android 11 Paste onto the drive works; on Android 9 the read-only note appears and Paste is not offered; unplugging returns to My files. Video was an H.264 MP4 and audio a WAV. Results per check: `docs/TESTING.md`.

## Security choices

- The browser transfer still reaches **only My files** (user decision). Device storage and USB are never exposed on the network.
- The content provider is not exported, is read-only, and only serves files under the library or shared storage.
- Recursive deletes always ask first and show the item count.
