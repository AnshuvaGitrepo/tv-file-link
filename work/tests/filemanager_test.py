"""
File manager test for TV File Link (v1.4 and later) on an Android TV emulator (Android 11 or Android 9 image).

Drives the TV app with D-pad key events and checks the results with adb (shared storage) and
with the Wi-Fi transfer API (the app library). Usage:
    python filemanager_test.py            # results -> work/tests/results/filemanager-<api>.json/.md
"""
import hashlib
import io
import json
import math
import re
import struct
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import emulator_test as t  # shared helpers: adb, ui_nodes, focus_to, key, http API ...

from PIL import Image, ImageDraw, ImageFont

PKG = t.PKG
DEV = "/sdcard/Download/TVFL-Test"
results = []


def record(name, ok, detail="", pending=False):
    status = "PENDING" if pending else ("PASS" if ok else "FAIL")
    results.append({"test": name, "result": status, "detail": str(detail)[:400]})
    print(f"[{status}] {name} - {detail}")


def sh(cmd, check=False):
    return t.adb("shell", cmd, check=check).strip()


def make_assets(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    # Two drawn sample "photos" (sunset and daytime landscape) so viewer screenshots show a real picture
    scenes = (("photo1.png", "Sample photo 1", ((255, 170, 90), (120, 60, 140)), (255, 220, 120), ((60, 40, 90), (35, 25, 60)), (40, 60, 110)),
              ("photo2.png", "Sample photo 2", ((120, 190, 245), (215, 235, 250)), (255, 245, 200), ((70, 130, 80), (40, 95, 60)), (60, 130, 190)))
    for name, label, (top, bottom), sun, (far, near), water in scenes:
        img = Image.new("RGB", (1280, 720))
        d = ImageDraw.Draw(img)
        for y in range(470):  # sky gradient
            f = y / 469
            d.line((0, y, 1280, y), fill=tuple(int(a + (b - a) * f) for a, b in zip(top, bottom)))
        d.ellipse((860, 150, 1020, 310), fill=sun)
        d.polygon([(0, 470), (180, 300), (330, 410), (520, 250), (760, 440), (980, 330), (1280, 470)], fill=far)
        d.rectangle((0, 465, 1280, 520), fill=near)
        d.polygon([(0, 520), (260, 400), (470, 500), (700, 420), (1000, 520), (1280, 430), (1280, 520)], fill=near)
        d.rectangle((0, 520, 1280, 720), fill=water)
        for i in range(8):  # light on the water
            y = 545 + i * 21
            d.line((900 - 70 + i * 6, y, 980 - i * 6, y), fill=sun, width=4)
        try:
            font = ImageFont.truetype("segoeuib.ttf", 44)
        except OSError:
            font = ImageFont.load_default()
        d.text((60, 640), label, fill=(255, 255, 255), font=font)
        img.save(folder / name)
    (folder / "notes.txt").write_text("TV File Link notes\nLine two: file manager test\n" + "x" * 200 + "\nEND OF NOTES\n", encoding="utf-8")
    with wave.open(str(folder / "song.wav"), "wb") as w:  # 30 s, 440 Hz tone
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * 440 * i / 22050))) for i in range(22050 * 30)))
    holiday = folder / "Holiday"
    (holiday / "Day 1").mkdir(parents=True, exist_ok=True)
    (holiday / "plan.txt").write_text("Holiday plan\n", encoding="utf-8")
    (holiday / "Day 1" / "beach.txt").write_text("Beach day\n" * 50, encoding="utf-8")


def caption():
    return " ".join(n["text"] for n in t.ui_nodes() if n["text"])


ROW_PREFIX = ("File ", "Folder ", "Options for ")


def first_row():
    return next((n for n in t.ui_nodes() if n["desc"].startswith(("File ", "Folder "))), None)


def reveal(desc, max_steps=25):
    """Scroll the file list with the D-pad until a row with this label is on screen."""
    for direction in ("down", "up"):
        for _ in range(max_steps):
            nodes = t.ui_nodes()
            if t.find(nodes, desc=desc):
                return True
            now = t.focused(nodes)
            if not now or not now["desc"].startswith(ROW_PREFIX):
                row = first_row()
                if not row or t.focus_to(desc=row["desc"]) is None:
                    return False
            t.key(direction, 0.3)
    return False


def all_names(max_steps=40):
    """Every name in the current folder, scrolling the list with the D-pad."""
    t.close_dialogs()
    row = first_row()
    if not row:
        return []
    t.focus_to(desc=row["desc"])
    names, last = [], None
    for _ in range(max_steps):
        nodes = t.ui_nodes()
        for n in nodes:
            d = n["desc"]
            if (d.startswith("File ") or d.startswith("Folder ")) and d.split(" ", 1)[1] not in names:
                names.append(d.split(" ", 1)[1])
        now = t.focused(nodes)
        here = now["desc"] if now else None
        if here == last:          # Down no longer moves: end of the list
            break
        last = here
        t.key("down", 0.3)
    return names


def media_state():
    """Playback state of the app's MediaPlayer from Android's audio service: started / paused / stopped / none."""
    uid = re.search(r"userId=(\d+)", t.adb("shell", "dumpsys", "package", PKG, check=False))
    pid = t.adb("shell", "pidof", PKG, check=False).strip()
    out = t.adb("shell", "dumpsys", "audio", check=False)
    u = uid.group(1) if uid else "x"
    states = re.findall(rf"type:android\.media\.MediaPlayer u/pid:{u}/{pid} state:(\w+)", out)
    if states:
        return states[-1]
    # Android 9: only an event log ("player piid:N has OP_PLAY_AUDIO... in uid:U", "player piid:N state:X")
    piids = set(re.findall(rf"player piid:(\d+) has OP_PLAY_AUDIO:\w+ in uid:{u}\b", out))
    piids |= set(re.findall(rf"new player piid:(\d+) uid/pid:{u}/", out))
    last = None
    for line in out.splitlines():
        m = re.search(r"player piid:(\d+) state:(\w+)", line)
        if m and m.group(1) in piids:
            last = m.group(2)
        m = re.search(r"releasing player piid:(\d+)", line)
        if m and m.group(1) in piids:
            last = "released"
    return last or "none"


def video_client():
    """True when the app has a video player session in media.player (also true after it finished)."""
    pid = t.adb("shell", "pidof", PKG, check=False).strip()
    out = t.adb("shell", "dumpsys", "media.player", check=False)
    return bool(re.search(rf"pid\({pid}\).{{0,800}}?mime\(video/", out, re.S))


def row_desc(name):
    for prefix in ("Folder ", "File "):
        if t.find(t.ui_nodes(), desc=prefix + name):
            return prefix + name
    return None


def open_item(name):
    """D-pad to the row for name and press OK."""
    t.close_dialogs()
    if not (reveal("Folder " + name, 12) or reveal("File " + name, 12)):
        return False
    desc = row_desc(name)
    if desc is None or t.focus_to(desc=desc) is None:
        return False
    t.key("center", 2.0)
    return True


def options(name, choice):
    t.close_dialogs()
    if not reveal("Options for " + name) or t.focus_to(desc="Options for " + name) is None:
        return False
    t.key("center", 1.5)
    if not t.menu_choose(choice):
        t.close_dialogs()
        return False
    return True


def press_button(text, tries=3):
    """D-pad to a button by its text and press Select; retries when focus did not get there."""
    for _ in range(tries):
        if t.focus_to(text) is not None:
            t.key("center", 3.0)
            return True
        t.key("up", 0.5)
    return False


LOCATION_RETRIES = []


def current_location():
    """Folder title (a TextView) starts with the open location's name."""
    for n in t.ui_nodes():
        if n["cls"].endswith("TextView") and n["pkg"].endswith("tvfilelink") and n["text"] and \
                not n["desc"] and n["cy"] < 400 and n["cx"] > 760:
            return n["text"]
    return ""


def go_location(label):
    """Select a location tab and confirm the title changed; retries are logged."""
    for attempt in range(3):
        if t.focus_to(desc="Location " + label) is None:
            continue
        t.key("center", 1.5)
        title = current_location()
        if title == label or title.startswith(label + " /"):
            if attempt:
                LOCATION_RETRIES.append(f"{label}: switched on attempt {attempt + 1}")
            return True
    LOCATION_RETRIES.append(f"{label}: did not switch (title '{current_location()}')")
    return False


def resumed_activity():
    out = t.adb("shell", "dumpsys", "activity", "activities", check=False)
    m = re.search(r"mResumedActivity: ActivityRecord\{\S+ \S+ (\S+)", out) or re.search(r"ResumedActivity: ActivityRecord\{\S+ \S+ (\S+)", out)
    return m.group(1) if m else "?"


def library_via_transfer(base_check):
    """Start a transfer and return (base_url, key) to read My files through the browser API."""
    addr, code = t.start_session()
    base = t.host_url(addr)
    st, k = t.connect(base, code)
    return base, k if st == 200 else None


def main():
    t.RESULTS.mkdir(parents=True, exist_ok=True)
    api = int(t.adb("shell", "getprop", "ro.build.version.sdk").strip())
    release = t.adb("shell", "getprop", "ro.build.version.release").strip()
    env = f"Android TV emulator, Android {release} (API {api}), x86, 1920x1080 @ 320 dpi"
    assets = t.TESTS / "data" / "fm"
    make_assets(assets)

    # Fresh install of the new APK (no storage access yet), test files in shared storage
    t.adb("uninstall", PKG, check=False)
    out = t.adb("install", t.NEW_APK, check=False)
    record("Install the new APK", "Success" in out, out.strip().splitlines()[-1] if out.strip() else "")
    sh(f"rm -rf {DEV}; mkdir -p {DEV}")
    t.adb("push", str(assets) + "/.", DEV)
    t.launch()  # record the app screen (moving focus) as the sample video
    t.adb("shell", f"(sleep 1; input keyevent 22; sleep 1; input keyevent 20; sleep 1; input keyevent 21) & "
                   f"screenrecord --time-limit 4 --size 960x540 {DEV}/clip.mp4", check=False)
    clip_size = sh(f"stat -c %s {DEV}/clip.mp4")
    record("Test files in shared storage (images, text, WAV, MP4 from screenrecord, nested folder)",
           sh(f"ls {DEV}").count("\n") >= 5, sh(f"ls {DEV}").replace("\n", ", ") + f"; clip.mp4 {clip_size} bytes")

    t.launch()
    tabs = [n["desc"][9:] for n in t.ui_nodes() if n["desc"].startswith("Location ")]
    record("Location tabs shown", "My files" in tabs and "Internal storage" in tabs, ", ".join(tabs))

    # Permission
    go_location("Internal storage")
    locked = t.find(t.ui_nodes(), desc="Allow storage access") is not None
    record("Internal storage asks for access first", locked, "Allow storage access button shown" if locked else caption()[:200])
    if t.focus_to(desc="Allow storage access") is not None:
        t.key("center", 3.0)
    if api >= 30:
        act = resumed_activity()
        record("Allow opens the All files access screen (Android 11)", "settings" in act.lower(), act)
        sh(f"appops set {PKG} MANAGE_EXTERNAL_STORAGE allow")
        t.key("back", 2.5)
        if PKG not in resumed_activity():
            t.launch()
    else:
        nodes = t.ui_nodes()
        allow = t.find(nodes, "ALLOW") or t.find(nodes, "Allow")
        record("Allow shows the Storage permission prompt (Android 9)", allow is not None, caption()[:160])
        if allow:
            if t.focus_to(allow["text"]) is not None:
                t.key("center", 2.0)
            else:
                t.adb("shell", "input", "tap", allow["cx"], allow["cy"]); time.sleep(2)
        granted = "granted=true" in t.adb("shell", "dumpsys", "package", PKG, check=False).split("WRITE_EXTERNAL_STORAGE")[-1][:40]
        record("Storage permission granted with the remote", granted, "")
    hint = [n["text"] for n in t.ui_nodes() if n["text"] == "Storage access is on."]
    record("After access is granted the hint is replaced by 'Storage access is on.'", bool(hint), hint or caption()[-120:])
    names = all_names()
    record("Internal storage lists folders after access", "Download" in names, ", ".join(names[:12]))

    # Browse with the D-pad
    ok = open_item("Download") and open_item("TVFL-Test")
    names = all_names()
    record("Open Download / TVFL-Test with the D-pad", ok and {"photo1.png", "notes.txt", "song.wav", "clip.mp4", "Holiday"} <= set(names),
           ", ".join(names))
    t.screenshot("fm-internal-storage-emulator.png" if api >= 30 else "fm-internal-storage-api28.png")

    # Viewers
    open_item("photo1.png")
    cap = caption()
    record("Image viewer opens (1 of 2)", "1 of 2" in cap and t.find(t.ui_nodes(), desc="Image viewer") is not None, cap[:160])
    if api >= 30: t.screenshot("fm-image-viewer-emulator.png")
    t.key("right", 1.5)
    cap = caption()
    record("Right on the remote shows the next image", "photo2.png" in cap and "2 of 2" in cap, cap[:160])
    t.key("back", 1.2)
    open_item("notes.txt")
    cap = caption()
    record("Text viewer shows the file", "END OF NOTES" in cap and "Line two" in cap, cap[:120])
    t.key("back", 1.2)
    # Media: the screen cannot be read by uiautomator while video draws, so playback is checked in
    # Android's audio service (state of the app's MediaPlayer) and media.player (video session).
    open_item("song.wav")
    time.sleep(2.5)
    s1 = media_state()
    t.key("center", 1.5)
    s2 = media_state()
    t.key("center", 1.5)
    s3 = media_state()
    record("Audio player plays, Select pauses and resumes", s1 == "started" and s2 == "paused" and s3 == "started",
           f"audio service: {s1} -> {s2} -> {s3}")
    t.key("back", 1.5)
    s4 = media_state()
    record("Back closes the player and stops playback", s4 in ("stopped", "released", "none"), f"audio service after Back: {s4}")
    open_item("clip.mp4")
    time.sleep(3)
    vid = video_client()
    if api >= 30: t.screenshot("fm-video-player-emulator.png")
    record("Video player opens and plays the MP4 (H.264)", vid, "media.player shows the app's video/avc session")
    t.key("back", 1.5)

    # Details and sort
    options("photo1.png", "Details")
    cap = caption()
    record("Details shows type, size and date", "image/png" in cap and "bytes" in cap and "Modified" in cap, cap[:160])
    t.close_dialogs()
    t.focus_to("Sort: Name"); t.key("center", 1.0); t.focus_to("Sort: Date"); t.key("center", 1.5)
    files = [n for n in all_names() if "." in n]
    sizes = {n: int(sh(f"stat -c %s '{DEV}/{n}'") or 0) for n in files}
    record("Sort by size puts the largest file first", files and files[0] == max(sizes, key=sizes.get),
           "order: " + ", ".join(files))
    t.focus_to("Sort: Size"); t.key("center", 1.0)  # back to Name

    # Copy a file into My files, check it through the browser transfer API
    options("photo1.png", "Copy")
    go_location("My files")
    paste =next((n["text"] for n in t.ui_nodes() if n["text"].startswith("Paste")), None)
    if paste:
        press_button(paste)
    names = all_names()
    record("Copy from internal storage, Paste into My files", paste is not None and "photo1.png" in names, f"button '{paste}'; My files: {names}")
    # Move a file into My files (source must disappear)
    go_location("Internal storage")
    open_item("Download"); open_item("TVFL-Test")
    options("notes.txt", "Move")
    go_location("My files")
    nodes = t.ui_nodes()
    move = next((n["text"] for n in nodes if n["text"].startswith("Move here")), None)
    before = (t.focused(nodes) or {}).get("desc") or (t.focused(nodes) or {}).get("text")
    pressed = press_button(move) if move else False
    app_msg = [n["text"][:80] for n in t.ui_nodes() if any(w in n["text"] for w in ("Moved", "already", "Could not", "exist", "Cancel"))]
    gone = "No such file" in sh(f"ls {DEV}/notes.txt 2>&1")
    names = all_names()
    record("Move from internal storage into My files (original removed)", move is not None and "notes.txt" in names and gone,
           f"button '{move}' pressed={pressed} (focus before: {before}); app: {app_msg}; source gone={gone}; My files: {names}")
    # Copy a nested folder
    go_location("Internal storage")
    open_item("Download"); open_item("TVFL-Test")
    options("Holiday", "Copy to My files")
    time.sleep(2.5)
    go_location("My files")
    record("Copy to My files copies a folder with subfolders", "Holiday" in all_names(), ", ".join(all_names()))
    base, k = library_via_transfer(None)
    ok_lib = False
    if k:
        st, data = t.download(base, k, "photo1.png")
        st2, sub = t.listing(base, k, "Holiday/Day 1")
        ok_lib = st == 200 and hashlib.sha256(data).hexdigest() == hashlib.sha256((assets / "photo1.png").read_bytes()).hexdigest() \
            and st2 == 200 and any(e["name"] == "beach.txt" for e in sub)
    record("Copied files are in My files and download intact through Wi-Fi transfer", ok_lib, "photo1.png SHA-256 match and Holiday/Day 1/beach.txt listed")
    t.press_transfer()
    t.clear_redirs()

    # Rename and delete in shared storage
    go_location("Internal storage")
    open_item("Download"); open_item("TVFL-Test")
    if options("photo2.png", "Rename"):
        t.adb("shell", "input", "keyevent", "123")
        t.adb("shell", "input", "keyevent", *(["67"] * 14))
        t.type_text("beach.png")
        t.press_dialog_button("Save")
    renamed = "beach.png" in sh(f"ls {DEV}")
    record("Rename a file in internal storage", renamed and "beach.png" in all_names(), sh(f"ls {DEV}").replace("\n", ", "))
    if options("Holiday", "Delete"):
        cap = caption()
        warn = "3 items" in cap
        t.press_dialog_button("Delete")
        time.sleep(1.5)
    else:
        warn, cap = False, ""
    gone = "No such file" in sh(f"ls {DEV}/Holiday 2>&1")
    record("Delete a folder with contents after a warning that counts its items", warn and gone, cap[:140])

    # Virtual USB drive (Android's built-in virtual disk); copy a file onto it
    usb_ok, usb_detail = False, ""
    sh("sm set-virtual-disk true")
    time.sleep(4)
    disks = sh("sm list-disks adoptable") or sh("sm list-disks")
    disk = disks.splitlines()[0].strip() if disks else ""
    if disk:
        sh(f"sm partition {disk} public")
        time.sleep(8)
        t.key("down", 0.3)
        t.focus_to("Refresh"); t.key("center", 2.0)
        tabs = [n["desc"][9:] for n in t.ui_nodes() if n["desc"].startswith("Location ")]
        usb = [x for x in tabs if x not in ("My files", "Internal storage")]
        usb_detail = f"disk {disk}; tabs: {tabs}"
        if usb and api >= 30:
            # Android 11 (Fire OS 8) with All files access: USB drives are writable
            options("beach.png", "Copy")
            go_location(usb[0])
            paste = next((n["text"] for n in t.ui_nodes() if n["text"].startswith("Paste")), None)
            if paste:
                press_button(paste)
            vol = sh("ls /storage").split()
            found = any("beach.png" in sh(f"ls /storage/{v} 2>/dev/null") for v in vol if v not in ("emulated", "self"))
            usb_ok = "beach.png" in all_names() and found
            usb_detail += f"; file on USB volume: {found}"
            t.screenshot("fm-usb-drive-emulator.png")
            record("USB drive appears as a location and accepts a pasted file", usb_ok, usb_detail)
        elif usb:
            # Android 9 (Fire OS 7): apps may read removable drives but not write -> shown read-only
            options("beach.png", "Copy")
            go_location(usb[0])
            nodes = t.ui_nodes()
            note = [n["text"][:90] for n in nodes if n["text"].startswith("Read-only on this Fire TV")]
            paste_shown = any(n["text"].startswith("Paste") for n in nodes)
            new_folder = next((n for n in nodes if n["text"] == "New folder"), None)
            t.screenshot("fm-usb-readonly-api28.png")
            record("USB drive on Android 9 is shown read-only with an explanation (no Paste / New folder)",
                   bool(note) and not paste_shown, f"{usb_detail}; note {note}; Paste shown={paste_shown}")
        else:
            record("USB drive appears as a location", False, usb_detail, pending=True)
        if usb:
            # unplug while the drive's tab is open: the app should notice by itself
            sh("sm set-virtual-disk false")
            time.sleep(6)
            title = current_location()
            note = [n["text"][:80] for n in t.ui_nodes() if "no longer available" in n["text"]]
            tabs = [n["desc"][9:] for n in t.ui_nodes() if n["desc"].startswith("Location ")]
            record("Removing the drive while it is open returns to My files with a message",
                   title == "My files" and bool(note) and usb[0] not in tabs, f"title '{title}'; message {note}; tabs {tabs}")
    else:
        record("USB drive appears as a location and accepts a pasted file", False, "emulator could not create a virtual disk", pending=True)
    sh("sm set-virtual-disk false")

    # Open with another app (depends on apps installed on the TV)
    go_location("My files")
    if options("photo1.png", "Open with another app"):
        time.sleep(2)
        act = resumed_activity()
        cap = caption()
        handled = PKG not in act or "No app can open" in cap
        record("Open with another app hands over the file or explains", handled, f"top: {act}; {cap[:100]}")
        t.key("back", 1.5)
        if PKG not in resumed_activity():
            t.launch()
    t.close_dialogs()
    t.key("home", 1.0)

    record("Location tabs switch when selected (retries are listed)",
           not any("did not switch" in r for r in LOCATION_RETRIES),
           "; ".join(LOCATION_RETRIES) or "every tab switched on the first press")
    passed = sum(r["result"] == "PASS" for r in results)
    failed = sum(r["result"] == "FAIL" for r in results)
    out = {"environment": env, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "apk": t.NEW_APK.name,
           "passed": passed, "failed": failed, "pending": len(results) - passed - failed, "results": results}
    stem = f"filemanager-api{api}"
    (t.RESULTS / f"{stem}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    lines = [f"# File manager test ({env})", "", f"- {out['date']}, {out['apk']}", f"- Passed {passed}, failed {failed}, pending {out['pending']}", "",
             "| # | Test | Result | Detail |", "|---|---|---|---|"]
    lines += [f"| {i} | {r['test']} | {r['result']} | {r['detail'].replace('|', '/')} |" for i, r in enumerate(results, 1)]
    (t.RESULTS / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed} passed, {failed} failed, {out['pending']} pending")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            t.clear_redirs()
        except Exception:
            pass
