"""Builds docs/TESTING.md from the JSON results in work/tests/results/."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "work" / "tests" / "results"
OUT = ROOT / "docs" / "TESTING.md"

SUITES = [
    ("emulator-results-api30", "Wi-Fi transfer", "Android 11 (API 30)"),
    ("emulator-results-api28", "Wi-Fi transfer", "Android 9 (API 28)"),
    ("filemanager-api30", "File manager", "Android 11 (API 30)"),
    ("filemanager-api28", "File manager", "Android 9 (API 28)"),
]

lines = [
    "# Testing",
    "",
    "All automated tests ran on the Windows build PC with Android TV emulators (x86, 1920x1080 @ 320 dpi).",
    "Android 11 matches Fire OS 8; Android 9 matches Fire OS 7. **No physical Fire TV or Vega device was available**;",
    "see *Pending* below.",
    "",
    "## How to run",
    "",
    "```powershell",
    "# Start an emulator (AVD TVFileLink_TV30 = Android 11, TVFileLink_TV28 = Android 9)",
    "& \"$env:ANDROID_HOME\\emulator\\emulator.exe\" -avd TVFileLink_TV30 -no-window -no-audio -no-snapshot -gpu swiftshader_indirect",
    "cd work\\tests",
    "$env:OLD_APK = \"<v1.2 APK with x86 code>\"   # for the upgrade check (the shipped v1.2 has no x86 code)",
    "python emulator_test.py        # Wi-Fi transfer: 38 checks",
    "python filemanager_test.py     # file manager",
    "python make_testing_md.py      # rebuild this file",
    "```",
    "",
    "How the tests work: the TV app is driven only with D-pad key events (`adb shell input keyevent`), and the screen",
    "is read with uiautomator. The browser side uses the same HTTP requests as the browser page, through an adb port",
    "forward and an on-device relay (the emulator gives the app the Wi-Fi address 10.0.2.16). Files are compared by",
    "SHA-256. While video is drawing, uiautomator cannot read the screen, so playback is checked in Android's",
    "`dumpsys audio` (player state) and `dumpsys media.player` (video session).",
    "",
    "## Summary",
    "",
    "Final run on the v1.4.1 release APK (16 November 2026), first attempt on both emulators. The only retry was a",
    "location tab that switched on the second key press (listed in the file manager results).",
    "",
    "| Suite | Emulator | Passed | Failed | Pending | Date |",
    "|---|---|---|---|---|---|",
]
details = []
for stem, title, emu in SUITES:
    f = RES / f"{stem}.json"
    if not f.exists():
        lines.append(f"| {title} | {emu} | - | - | - | not run |")
        continue
    data = json.loads(f.read_text(encoding="utf-8"))
    res = data["results"]
    p = sum(r["result"] == "PASS" for r in res)
    pend = sum(r["result"] == "PENDING" for r in res)
    fail = len(res) - p - pend
    date = data.get("date") or data["environment"].get("date", "")
    lines.append(f"| {title} | {emu} | {p} | {fail} | {pend} | {date} |")
    details += ["", f"## {title}: {emu}", "", "| # | Check | Result | Detail |", "|---|---|---|---|"]
    for i, r in enumerate(res, 1):
        d = " ".join(r["detail"].split()).replace("|", "/")
        details.append(f"| {i} | {r['test']} | {r['result']} | {d[:160]} |")

lines += details
lines += [
    "",
    "## Also verified on the build PC",
    "",
    "- APK: v2 + v3 signature, certificate SHA-256 `237eabf4...d4ac8ccf` (same as v1.2), versionCode 6 / 1.4.1, zipalign, ARM 32/64-bit libraries.",
    "- Vega: `npm run typecheck` and `react-native bundle --platform kepler` succeed; shared C++ compiles for ARM64.",
    "",
    "## Pending (needs hardware)",
    "",
    "| Test | What is needed |",
    "|---|---|",
    "| Fire OS on a physical Fire TV Stick (ARM): install, update, remote, transfer, file manager | Stick with ADB debugging, computer on the same network |",
    "| Fire OS 8 All files access screen on a real Fire TV | Fire OS 8 device |",
    "| Real USB drive (OTG) on a Stick | FAT32/exFAT drive + OTG adapter (the emulator used Android's virtual disk) |",
    "| Writing to USB on Fire OS 6/7 | Storage Access Framework grant in the app (follow-up); read-only today, by design |",
    "| Video formats on hardware (MKV, HEVC, 4K) | Sample files on the Stick (emulator: H.264 MP4 and WAV only) |",
    "| Transfer between two separate devices; per-device key on two phones | Stick + two phones on home Wi-Fi |",
    "| Number keypad on iPhone and Android phones | Real phones (Chrome check: `inputmode=numeric`) |",
    "| Storage-full message | Nearly full Stick |",
    "| Vega VPKG build + device test (incoming connections, library file manager) | Ubuntu/macOS + Vega SDK, Vega device (see VEGA-BUILD.md) |",
    "| Large file (> 1 GB) on 32-bit ARM | cpp-httplib warns about 32-bit builds; the 32-bit x86 emulator passed |",
    "",
]
OUT.parent.mkdir(exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT)
