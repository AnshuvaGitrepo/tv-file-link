"""
End-to-end test of TV File Link on the Android TV emulator.

The TV app is driven with D-pad key events (adb). The Windows host acts as the
phone/computer browser: the emulator console forwards a host port to the app's
transfer port, and the test talks to the same HTTP API the browser page uses.

Usage: python -I emulator_test.py
Writes: work/tests/results/emulator-results.json and .md, screenshots/ (TV captures)
"""
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
RESULTS = TESTS / "results"
SHOTS = Path(os.environ.get("SHOTS_DIR", str(ROOT / "screenshots")))  # set for extra emulators
DATA = TESTS / "data"
ADB = Path(os.environ["ANDROID_HOME"]) / "platform-tools" / "adb.exe"
PKG = "com.anshuva.tvfilelink"
NEW_APK = ROOT / "fire-os" / "TV-File-Link-Fire-OS.apk"
# The shipped v1.2 has no x86 library; for the x86 TV emulator pass a v1.2 rebuilt from the
# unchanged v1.2 source with x86 added and the same key (OLD_APK environment variable).
OLD_APK = Path(os.environ.get("OLD_APK", ROOT / "work" / "releases" / "TV-File-Link-Fire-OS-v1.2.apk"))
KEY = {"up": 19, "down": 20, "left": 21, "right": 22, "center": 23, "back": 4, "home": 3}

results = []
redirs = []


def record(name, ok, detail=""):
    results.append({"test": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} - {detail}")


def adb(*args, check=True, binary=False, timeout=120):
    out = subprocess.run([str(ADB), *map(str, args)], capture_output=True, timeout=timeout)
    if check and out.returncode != 0:
        raise RuntimeError(f"adb {' '.join(map(str, args))}: {out.stderr.decode(errors='replace')}")
    return out.stdout if binary else out.stdout.decode(errors="replace")


def key(name, pause=0.6):
    adb("shell", "input", "keyevent", KEY[name])
    time.sleep(pause)


# ------------------------------------------------------------------ UI helpers
def ui_nodes():
    """Current screen. Returns [] when uiautomator cannot capture it (e.g. while video plays),
    instead of re-reading an older dump."""
    xml = ""
    for _ in range(5):  # Android 9 sometimes reports "null root node" for a moment
        adb("shell", "rm", "-f", "/data/local/tmp/ui.xml", check=False)
        adb("shell", "uiautomator", "dump", "/data/local/tmp/ui.xml", check=False)
        xml = adb("exec-out", "cat", "/data/local/tmp/ui.xml", check=False)
        if xml.strip().startswith("<?xml"):
            break
        time.sleep(1)
    if "<?xml" not in xml:
        return []
    nodes = []
    for n in ET.fromstring(xml[xml.index("<?xml"):]).iter("node"):
        b = [int(v) for v in re.findall(r"\d+", n.get("bounds", "[0,0][0,0]"))]
        nodes.append({"text": n.get("text", ""), "desc": n.get("content-desc", ""),
                      "focused": n.get("focused") == "true", "cls": n.get("class", ""),
                      "pkg": n.get("package", ""), "bounds": b,
                      "cx": (b[0] + b[2]) // 2, "cy": (b[1] + b[3]) // 2})
    return nodes


def find(nodes, text=None, desc=None, exact=True):
    for n in nodes:  # dialog buttons are drawn in capitals (SAVE, DELETE), so ignore case
        if text is not None and (n["text"].casefold() == text.casefold() if exact else text in n["text"]):
            return n
        if desc is not None and (n["desc"] == desc if exact else desc in n["desc"]):
            return n
    return None


def focused(nodes):
    hits = [n for n in nodes if n["focused"]]
    return hits[-1] if hits else None


CONTAINERS = ("ScrollView", "ListView", "LinearLayout", "FrameLayout", "RecyclerView", "HorizontalScrollView")


def on_target(now, target):
    """Focus is on the target when the focused element covers its centre and is not a big container
    (Android 9 dialogs first focus the message ScrollView, which spans the buttons)."""
    b = now["bounds"]
    covers = b[0] <= target["cx"] <= b[2] and b[1] <= target["cy"] <= b[3]
    area = max(1, (b[2] - b[0]) * (b[3] - b[1]))
    t_area = max(1, (target["bounds"][2] - target["bounds"][0]) * (target["bounds"][3] - target["bounds"][1]))
    return covers and not now["cls"].endswith(CONTAINERS) and area <= 2.5 * t_area


def focus_to(text=None, desc=None, steps=16):
    """Move the D-pad focus onto the element; returns number of key presses or None."""
    previous, swap, stalls = None, False, 0
    for i in range(steps):
        nodes = ui_nodes()
        if not nodes:                # screen could not be read this moment: wait, do not give up
            time.sleep(0.7)
            continue
        target, now = find(nodes, text, desc), focused(nodes)
        if target is None:
            return None
        if now and (now["bounds"] == target["bounds"] or on_target(now, target)):
            return i
        if now is None:
            key("down")
            continue
        stalls = stalls + 1 if previous == now["bounds"] else 0
        if stalls >= 2:              # two keys in a row did not move focus: try the other axis
            swap, stalls = not swap, 0
        previous = now["bounds"]
        dy, dx = target["cy"] - now["cy"], target["cx"] - now["cx"]
        # The transfer rail ends at about x=760 (1080p); the file panel is to its right.
        other_panel = (target["cx"] < 760) != (now["cx"] < 760)
        horizontal = other_panel or abs(dy) <= 25   # other panel: cross over first
        if swap and abs(dx) > 25 and abs(dy) > 25:
            horizontal = not horizontal
        if horizontal:
            key("right" if dx > 0 else "left", 0.4)
        else:
            key("down" if dy > 0 else "up", 0.4)
    return None


def screenshot(name):
    SHOTS.mkdir(exist_ok=True)
    (SHOTS / name).write_bytes(adb("exec-out", "screencap", "-p", binary=True))


def session_info():
    nodes = ui_nodes()
    addr = next((n["text"] for n in nodes if n["text"].startswith("http://")), None)
    code = next((n["text"] for n in nodes if re.fullmatch(r"\d{6}", n["text"])), None)
    return addr, code


def launch():
    adb("shell", "am", "start", "-W", "-n", f"{PKG}/.MainActivity")
    time.sleep(2.5)


def press_transfer():
    """Focus the Start/Stop transfer button and press it with the remote."""
    label = "Stop transfer" if find(ui_nodes(), "Stop transfer") else "Start transfer"
    if focus_to(label) is None:
        raise RuntimeError("Could not focus " + label)
    key("center", 2.0)


def start_session():
    nodes = ui_nodes()
    if find(nodes, "Stop transfer"):
        return session_info()
    press_transfer()
    for _ in range(10):
        addr, code = session_info()
        if addr and code:
            return addr, code
        time.sleep(1)
    raise RuntimeError("Transfer did not start")


# ------------------------------------------------------------------ emulator port forwarding
def console(*commands):
    token = (Path.home() / ".emulator_console_auth_token").read_text().strip()
    with socket.create_connection(("127.0.0.1", 5554), timeout=10) as s:
        def read():
            time.sleep(0.4)
            s.settimeout(2)
            data = b""
            try:
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if data.rstrip().endswith(b"OK") or b"KO" in data:
                        break
            except socket.timeout:
                pass
            return data.decode(errors="replace")
        read()
        s.sendall(f"auth {token}\r\n".encode())
        read()
        out = ""
        for c in commands:
            s.sendall((c + "\r\n").encode())
            out += read()
        s.sendall(b"quit\r\n")
        return out


def host_url(addr):
    """Make the app's transfer address reachable from the Windows host.

    The emulator gives the app a Wi-Fi address (10.0.2.16) that the console 'redir' cannot reach,
    so: host port --adb forward--> device 127.0.0.1:relay --nc--> app address:port.
    """
    ip, port = addr[len("http://"):].rsplit(":", 1)
    if port not in redirs:
        relay = 18000 + len(redirs)
        subprocess.Popen([str(ADB), "shell", f"toybox nc -s 127.0.0.1 -p {relay} -L toybox nc {ip} {port}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)
        adb("forward", f"tcp:{port}", f"tcp:{relay}")
        redirs.append(port)
    return f"http://127.0.0.1:{port}"


def clear_redirs():
    if redirs:
        adb("forward", "--remove-all", check=False)
        adb("shell", "pkill -f 'nc -s 127.0.0.1'", check=False)
        redirs.clear()
        time.sleep(0.5)


# ------------------------------------------------------------------ HTTP (what the browser does)
def http(method, url, headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def connect(base, code):
    st, body = http("POST", base + "/api/connect", {"X-TV-Code": code})
    return st, (json.loads(body) if st == 200 else body.decode(errors="replace"))


def q(**params):
    return urllib.parse.urlencode(params)


def upload(base, k, folder, name, payload):
    return http("POST", f"{base}/api/upload?{q(path=folder, name=name)}",
                {"X-Transfer-Key": k, "Content-Type": "application/octet-stream"}, payload, timeout=120)


def listing(base, k, folder=""):
    st, body = http("GET", f"{base}/api/list?{q(path=folder)}", {"X-Transfer-Key": k})
    return st, (json.loads(body) if st == 200 else body.decode(errors="replace"))


def download(base, k, path):
    return http("GET", f"{base}/api/download?{q(path=path, key=k)}", timeout=120)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def refused(base):
    try:
        st, _ = http("GET", base + "/", timeout=5)
        return False
    except Exception:  # refused, reset, or the relay's own "connection refused" text
        return True


# ------------------------------------------------------------------ dialogs on the TV
def type_text(text):
    adb("shell", "input", "text", text.replace(" ", "%s"))
    time.sleep(0.8)


def press_dialog_button(label):
    """Press a dialog button with the D-pad; tap only if focus cannot reach it."""
    now = focused(ui_nodes())
    if now and now["cls"].endswith("EditText"):
        key("back", 1.0)  # like the remote: Back closes the on-screen keyboard, the dialog stays
    if find(ui_nodes(), label) is None:
        return "missing"
    if focus_to(label) is not None:
        key("center", 1.5)
        return "dpad"
    n = find(ui_nodes(), label)
    adb("shell", "input", "tap", n["cx"], n["cy"])
    time.sleep(1.5)
    return "tap"


def close_dialogs():
    """Press Back until the main screen (with the transfer button) is showing again."""
    for _ in range(3):
        nodes = ui_nodes()
        if find(nodes, "Start transfer") or find(nodes, "Stop transfer"):
            if not any(n["text"] in ("SAVE", "CANCEL", "DELETE", "OK") or n["text"] in MENU[1:] for n in nodes):
                return
        key("back", 0.8)


MENU = ("Open", "Open with another app", "Copy", "Move", "Rename", "Delete", "Details",
        "Copy to My files", "Download to a phone or computer")


def tv_names():
    """Names of the files and folders listed on the TV (from each row's accessibility label)."""
    close_dialogs()
    out = []
    for n in ui_nodes():
        d = n["desc"]
        if d.startswith("File ") or d.startswith("Folder "):
            out.append(d.split(" ", 1)[1])
    return out


def menu_choose(choice):
    """In an open Options menu: Down to the item (highlight starts on the first item), then OK."""
    items = [n["text"] for n in ui_nodes() if n["cls"].endswith("TextView") and n["text"] in MENU]
    if choice not in items:
        return False
    for _ in range(items.index(choice)):
        key("down", 0.4)
    key("center", 1.5)
    return True


# ------------------------------------------------------------------ main test
def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    abi = adb("shell", "getprop", "ro.product.cpu.abilist").strip()
    release = adb("shell", "getprop", "ro.build.version.release").strip()
    env = {"emulator": "Android TV emulator (Android " + release + ", ABI " + abi + ", 1920x1080 @ 320 dpi)",
           "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "apk": NEW_APK.name}

    # 1. Upgrade path: install v1.2, store a file with it, then install v1.3 over it.
    adb("uninstall", PKG, check=False)
    adb("install", OLD_APK)
    launch()
    addr, code = start_session()
    base = host_url(addr)
    st, k = connect(base, code)
    old_payload = b"Stored by v1.2 before the update.\n" * 100
    st2, _ = upload(base, k, "", "kept-from-v1.2.txt", old_payload)
    record("v1.2 baseline: upload a file with the old release", st == 200 and st2 == 201, f"connect {st}, upload {st2}")
    key("home", 1.5)
    clear_redirs()
    out = adb("install", "-r", NEW_APK, check=False)
    ver = re.search(r"versionName=(\S+)", adb("shell", "dumpsys", "package", PKG))
    expected = re.search(r'VERSION_NAME = "[^"]*", "([^"]+)"', (ROOT / "fire-os" / "build-apk.py").read_text(encoding="utf-8"))
    expected = expected.group(1) if expected else "?"
    record("Update installs over v1.2 (same app ID and signing key)",
           "Success" in out and ver and ver.group(1) == expected,
           out.strip().splitlines()[-1] + f"; versionName={ver.group(1) if ver else '?'} (expected {expected})")

    # 2. First run of v1.3 + remote navigation
    launch()
    nodes = ui_nodes()
    record("v1.2 file still listed after the update", "kept-from-v1.2.txt" in tv_names(),
           "My files shows: " + ", ".join(tv_names()))
    f = focused(nodes)
    record("App opens with remote focus on Start transfer", f is not None and f["text"] == "Start transfer",
           f"focused: {f['text'] if f else None}")
    screenshot("tv-home-emulator.png")
    path_keys = []
    for target in ("Refresh", "New folder", "Start transfer"):
        steps = focus_to(target)
        path_keys.append(f"{target}: {steps} key presses" if steps is not None else f"{target}: unreachable")
    record("D-pad reaches transfer and file controls", all("unreachable" not in p for p in path_keys), "; ".join(path_keys))

    # 3. Folder operations on the TV with the remote
    focus_to("New folder")
    key("center", 1.5)
    type_text("Photos")
    how = press_dialog_button("Save")
    record("Create folder 'Photos' on the TV", "Photos" in tv_names(), f"Save pressed via {how}")

    # 4. Start transfer, read address and code from the TV screen
    addr, code = start_session()
    record("Start transfer shows address and six-digit code",
           bool(re.fullmatch(r"http://\d+\.\d+\.\d+\.\d+:\d+", addr or "")) and bool(re.fullmatch(r"\d{6}", code or "")),
           f"address {addr}, code {code}")
    screenshot("tv-transfer-active-emulator.png")
    base = host_url(addr)

    st, body = http("GET", base + "/")
    record("Browser page loads from the TV address", st == 200 and b"6-digit TV code" in body, f"HTTP {st}, {len(body)} bytes")
    st, body = listing(base, "")
    record("File list refused without connecting", st == 403, f"HTTP {st}")
    st, k = connect(base, code)
    record("Correct code connects", st == 200 and isinstance(k, str) and len(k) == 32, f"HTTP {st}")

    # 5. Upload, list, download, compare
    files = {
        "Holiday video.bin": os.urandom(6 * 1024 * 1024 + 123),
        "Travel itinerary.txt": ("Day 1: Kolkata\nDay 2: Darjeeling\n" * 200).encode(),
        "notes 0123.txt": b"leading zero name check\n",
    }
    for name, payload in files.items():
        (DATA / name).write_bytes(payload)
    for name, payload in files.items():
        folder = "Photos" if name.endswith(".bin") else ""
        st, body = upload(base, k, folder, name, payload)
        record(f"Upload '{name}' ({len(payload):,} bytes) to {'Photos' if folder else 'My files'}", st == 201, f"HTTP {st}")
    st, root_list = listing(base, k, "")
    st2, photo_list = listing(base, k, "Photos")
    root_names = [e["name"] for e in root_list] if st == 200 else [str(root_list)]
    photo_names = [e["name"] for e in photo_list] if st2 == 200 else [str(photo_list)]
    record("Uploaded files appear in the right folders",
           st == 200 and st2 == 200 and {"Travel itinerary.txt", "notes 0123.txt", "Photos"} <= set(root_names)
           and "Holiday video.bin" in photo_names,
           f"root: {root_names}; Photos: {photo_names}")
    for name, payload in files.items():
        p = ("Photos/" if name.endswith(".bin") else "") + name
        st, data = download(base, k, p)
        record(f"Download '{name}' and compare SHA-256", st == 200 and sha(data) == sha(payload),
               f"sent {sha(payload)[:16]}..., received {sha(data)[:16]}...")
    st, data = download(base, k, "kept-from-v1.2.txt")
    record("Download the file stored by v1.2", st == 200 and data == old_payload, f"HTTP {st}, match={data == old_payload}")

    # 6. Errors
    st, body = upload(base, k, "", "Travel itinerary.txt", b"again")
    record("Duplicate name is refused with a clear message", st == 409 and b"already exists" in body,
           f"HTTP {st}: {body.decode(errors='replace')}")
    st, body = listing(base, k, "../")
    record("Path outside the library is refused", st == 400, f"HTTP {st}: {body}")
    st, body = download(base, "0" * 32, "Travel itinerary.txt")
    record("Download with a made-up key is refused", st == 403, f"HTTP {st}")
    st, body = http("POST", f"{base}/api/upload?{q(path='', name='huge.bin')}",
                    {"X-Transfer-Key": k, "Content-Type": "application/octet-stream",
                     "Content-Length": str(3 * 1024 ** 3)}, b"x", timeout=20)
    record("Upload over the 2 GiB limit is refused", st in (413, 400), f"HTTP {st}")
    st, body = upload(base, k, "Missing folder", "a.txt", b"x")
    record("Upload to a folder that no longer exists is refused", st == 404, f"HTTP {st}: {body.decode(errors='replace')}")

    # 7. Browser screenshots with the real page (phone + desktop)
    profile = Path(os.environ.get("TEMP", str(TESTS))) / "tvfilelink-chrome-profile"
    cap = subprocess.run(["node", str(TESTS / "capture-browser.mjs"), base, code, str(SHOTS), str(profile)],
                         capture_output=True, text=True, timeout=180)
    try:
        info = json.loads(cap.stdout.strip().splitlines()[-1])
    except Exception:
        info = {"error": (cap.stderr or cap.stdout)[-300:]}
    record("Real browser connects and shows the file list (Chrome)", "rows" in info and len(info["rows"]) >= 3,
           json.dumps(info)[:380])
    record("Code box asks phones for the numeric keypad",
           info.get("inputmode") == "numeric" and info.get("inputType") == "text", f"inputmode={info.get('inputmode')}, type={info.get('inputType')}")

    # 8. TV shows browser uploads by itself, then rename and delete with the remote
    seen = False
    for _ in range(10):
        if "notes 0123.txt" in tv_names():
            seen = True
            break
        time.sleep(1)
    record("TV list shows browser uploads without pressing Refresh", seen, "names: " + ", ".join(tv_names()))
    screenshot("tv-transfer-files-emulator.png")

    def options(item, choice):
        """Remote: focus 'Options' for item, press OK, pick choice from the menu."""
        close_dialogs()
        if focus_to(desc="Options for " + item) is None:
            return False
        key("center", 1.5)
        if not menu_choose(choice):
            close_dialogs()
            return False
        return True

    ok = options("notes 0123.txt", "Rename")
    if ok:
        adb("shell", "input", "keyevent", "123")  # cursor to the end, then delete the old name
        adb("shell", "input", "keyevent", *(["67"] * 20))
        type_text("renamed-notes.txt")
        how = press_dialog_button("Save")
    names = tv_names()
    record("Rename a file on the TV", ok and "renamed-notes.txt" in names and "notes 0123.txt" not in names,
           f"menu reached={ok}; now: {names}")
    # v1.4: a folder with files can be deleted after a warning that counts the items inside
    ok = options("Photos", "Delete")
    msg = " ".join(n["text"] for n in ui_nodes() if "item" in n["text"] and "deleted" in n["text"]) if ok else ""
    how = press_dialog_button("Delete") if ok else "menu not reached"
    record("Deleting a folder with files warns with the item count, then deletes it",
           ok and "1 item" in msg and "Photos" not in tv_names(), f"via {how}; warning: {msg}")
    before = "renamed-notes.txt" in tv_names()
    ok = options("renamed-notes.txt", "Delete")
    if ok:
        screenshot("tv-delete-confirm-emulator.png")
    how = press_dialog_button("Delete") if ok else "menu not reached"
    record("Delete a file after confirmation", before and ok and "renamed-notes.txt" not in tv_names(), f"via {how}")
    close_dialogs()
    focus_to("New folder")
    key("center", 1.5)
    type_text("Empty")
    press_dialog_button("Save")
    before = "Empty" in tv_names()
    ok = options("Empty", "Delete")
    how = press_dialog_button("Delete") if ok else "menu not reached"
    record("Delete an empty folder after confirmation", before and ok and "Empty" not in tv_names(), f"via {how}")
    close_dialogs()

    # 9. Stop transfer closes the session
    old_base, old_key = base, k
    press_transfer()
    time.sleep(1.5)
    record("Stop transfer closes the server", refused(old_base) and find(ui_nodes(), "Start transfer") is not None,
           "connection refused after Stop")
    clear_redirs()

    # 10. Wrong codes and rate limit (new session = fresh counters)
    addr, code = start_session()
    base = host_url(addr)
    wrong = f"{(int(code) + 1) % 1000000:06d}"
    st1, b1 = connect(base, wrong)
    st2, b2 = connect(base, wrong)
    st3, b3 = connect(base, wrong)
    st4, b4 = connect(base, code)
    record("Wrong code is refused", st1 == 403 and "not correct" in b1, f"HTTP {st1}: {b1}")
    record("After 3 wrong codes, even the right code must wait", st4 == 429 and "Wait" in str(b4), f"HTTP {st4}: {b4}")
    time.sleep(2.2)
    st5, k5 = connect(base, code)
    record("Right code works after the short wait", st5 == 200, f"HTTP {st5}")
    st, _ = listing(base, old_key, "")
    record("Key from the previous session is refused", st == 403, f"HTTP {st}")

    # 11. Leading-zero code
    found = None
    for attempt in range(80):
        if code.startswith("0"):
            found = (attempt, addr, code)
            break
        press_transfer()  # stop
        clear_redirs()
        addr, code = start_session()
    if found:
        base = host_url(found[1])
        st, _ = connect(base, found[2])
        record("Code with a leading zero is shown in full and accepted", st == 200 and len(found[2]) == 6,
               f"code {found[2]} after {found[0]} restarts, HTTP {st}")
        screenshot("tv-leading-zero-code-emulator.png")
    else:
        record("Code with a leading zero is shown in full and accepted", False, "no leading-zero code in 80 restarts")

    # 12. Leaving the app closes the session
    key("home", 2.0)
    record("Leaving the app (Home) closes the server", refused(base), "connection refused after Home")
    clear_redirs()
    launch()
    record("Reopened app shows Start transfer (no session)", find(ui_nodes(), "Start transfer") is not None, "")
    key("home", 1.0)

    passed = sum(r["result"] == "PASS" for r in results)
    summary = {"environment": env, "passed": passed, "failed": len(results) - passed, "results": results}
    api = adb("shell", "getprop", "ro.build.version.sdk").strip()
    lines = [f"# Wi-Fi transfer test results", "", f"- Environment: {env['emulator']}", f"- Date: {env['date']}",
             f"- APK: {env['apk']}", f"- Passed {passed} / {len(results)}", "", "| # | Test | Result | Detail |", "|---|---|---|---|"]
    lines += [f"| {i} | {r['test']} | {r['result']} | {r['detail'].replace('|', '/')} |" for i, r in enumerate(results, 1)]
    for stem in ("emulator-results", f"emulator-results-api{api}"):  # latest + per Android version
        (RESULTS / f"{stem}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
        (RESULTS / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} passed")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            clear_redirs()
        except Exception:
            pass
