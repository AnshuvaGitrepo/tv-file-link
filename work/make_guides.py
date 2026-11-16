"""Build the two branded TV File Link PDFs (User Guide, Installation and Testing Guide).

Branding follows the approved OpenSSH briefing: navy cover, framed gold-and-silver AS logo,
subtle blue circuit traces, version badge, light interior pages, compact running header,
numbered pages and the footer "Prepared by Anshuva Samanta".
"""
import json
from pathlib import Path

from pypdf import PdfReader
from reportlab import rl_config
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

rl_config.useA85 = 0  # binary image streams: smaller, and no random text for the leak scanner to misread

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "screenshots"
RESULTS = json.loads((ROOT / "work" / "tests" / "results" / "emulator-results.json").read_text(encoding="utf-8"))
W, H = letter
M = 45
INNER = W - 2 * M
BOTTOM = 734  # content must end above the footer rule (746)
VERSION, DATE = "v1.4.1", "16 November 2026"

for name, file in [("UI", "segoeui.ttf"), ("UI-Bold", "segoeuib.ttf"), ("Mono", "consola.ttf"), ("Mono-Bold", "consolab.ttf")]:
    pdfmetrics.registerFont(TTFont(name, "C:/Windows/Fonts/" + file))
pdfmetrics.registerFontFamily("UI", normal="UI", bold="UI-Bold")

INK, SUB, NAVY = "#152844", "#405673", "#0b192d"
GOLD, RULE, PAPER, WHITE = "#ffd174", "#cfdeee", "#f0f5fb", "#ffffff"
CYAN, BLUE, GREEN, AMBER, RED = "#7bdcf3", "#065f9e", "#087a72", "#b26712", "#b3261e"
LOGO = ImageReader(str(ROOT / "shared" / "as-logo.png"))

LINKS = {
    "adb": "https://developer.amazon.com/docs/fire-tv/connecting-adb-to-device.html",
    "install": "https://developer.amazon.com/docs/fire-tv/installing-and-running-your-app.html",
    "vega_sdk": "https://developer.amazon.com/docs/vega/0.23/install-vega-sdk.html",
    "vega_build": "https://developer.amazon.com/docs/vega/0.24/build-an-app.html",
    "vega_run": "https://developer.amazon.com/docs/vega/0.24/run-apps.html",
    "vega_manifest": "https://developer.amazon.com/docs/vega/0.24/app-manifest.html",
    "vega_fs": "https://developer.amazon.com/docs/vega-api/0.24/README.amazon-devices_kepler-file-system.html",
}


class Doc:
    def __init__(self, out, title, subject, kicker, header_title, total):
        self.out, self.kicker, self.header_title, self.total = out, kicker, header_title, total
        self.c = canvas.Canvas(str(out), pagesize=letter, pageCompression=1)
        self.c.setTitle(title)
        self.c.setAuthor("Anshuva Samanta")
        self.c.setSubject(subject)
        self.page = 0

    # ---- primitives (top-based coordinates)
    def rect(self, x, top, w, h, fill, radius=0, stroke=None):
        c = self.c
        c.setFillColor(HexColor(fill))
        if stroke:
            c.setStrokeColor(HexColor(stroke))
            c.setLineWidth(.7)
        if radius:
            c.roundRect(x, H - top - h, w, h, radius, fill=1, stroke=bool(stroke))
        else:
            c.rect(x, H - top - h, w, h, fill=1, stroke=bool(stroke))

    def line(self, x1, x2, top, color=RULE):
        self.c.setStrokeColor(HexColor(color))
        self.c.setLineWidth(.7)
        self.c.line(x1, H - top, x2, H - top)

    def text(self, content, x, top, w, size=11, leading=15, color=INK, bold=False, font=None):
        style = ParagraphStyle("t", fontName=font or ("UI-Bold" if bold else "UI"), fontSize=size,
                               leading=leading, textColor=HexColor(color))
        p = Paragraph(content, style)
        _, h = p.wrap(w, H)
        p.drawOn(self.c, x, H - top - h)
        return top + h

    def label(self, content, x, top, color=CYAN, size=8.5):
        c = self.c
        c.saveState()
        t = c.beginText(x, H - top - size)
        t.setFont("UI-Bold", size)
        t.setFillColor(HexColor(color))
        t.setCharSpace(1.2)
        t.textLine(content)
        c.drawText(t)
        c.restoreState()

    def trace(self, pts, color="#285276", width=.7):
        self.c.setStrokeColor(HexColor(color))
        self.c.setLineWidth(width)
        self.c.lines([(ax, H - ay, bx, H - by) for (ax, ay), (bx, by) in zip(pts, pts[1:])])

    def dot(self, x, y, r, color):
        self.c.setFillColor(HexColor(color))
        self.c.circle(x, H - y, r, stroke=0, fill=1)

    def framed_logo(self, x, top, side):
        self.rect(x, top, side, side, "#10243b", 10, "#c9a95b")
        path = self.c.beginPath()
        path.roundRect(x + 1.5, H - top - side + 1.5, side - 3, side - 3, 9)
        self.c.saveState()
        self.c.clipPath(path, stroke=0, fill=0)
        self.c.drawImage(LOGO, x + 1.5, H - top - side + 1.5, side - 3, side - 3)
        self.c.restoreState()

    def pic(self, name, x, top, w, border=True, max_h=None):
        img = ImageReader(str(SHOTS / name))
        ow, oh = img.getSize()
        h = w * oh / ow
        if max_h and h > max_h:  # keep inside the column: shrink and centre
            nw = max_h * ow / oh
            x, w, h = x + (w - nw) / 2, nw, max_h
        if border:
            self.rect(x - 2, top - 2, w + 4, h + 4, "#ffffff", 6, "#b9cbe0")
        self.c.drawImage(img, x, H - top - h, w, h)
        return top + h

    def link(self, label_text, url, x, top, w, size=10):
        bottom = self.text(f'<font color="{BLUE}"><u>{label_text}</u></font>', x, top, w, size, size + 4)
        self.c.linkURL(url, (x, H - bottom, x + min(w, pdfmetrics.stringWidth(label_text, "UI", size) + 2), H - top), relative=0)
        return bottom

    # ---- page furniture
    def badge(self, x, y, w, cover=False):
        self.rect(x, y, w, 38 if cover else 27, "#102842", 9, "#315579")
        self.dot(x + 12, y + 12, 1.8, GOLD)
        if cover:
            self.label("GUIDE EDITION", x + 21, y + 5, GOLD, 7.2)
            self.text(f"{VERSION}  /  {DATE}", x + 12, y + 19, w - 23, 9.4, 12, WHITE)
        else:
            self.text(f"{VERSION}  /  {DATE}", x + 20, y + 7, w - 24, 8.2, 12, WHITE)

    def footer(self, dark=False):
        tone = "#acc0d6" if dark else SUB
        self.line(M, W - M, 746, "#315172" if dark else RULE)
        self.text("TV File Link  /  Prepared by Anshuva Samanta", M, 755, 385, 8.5, 12, tone, True)
        self.text(f"{self.page:02d} / {self.total:02d}", W - M - 40, 755, 40, 8.5, 12, tone, True)

    def new_page(self, section=None, key=None):
        if self.page:
            self.c.showPage()
        self.page += 1
        if section is None:
            return
        if key:
            self.c.bookmarkPage(key)
            self.c.addOutlineEntry(section.title(), key, level=0)
        self.rect(0, 0, W, H, PAPER)
        self.rect(0, 0, W, 66, NAVY)
        self.framed_logo(M, 12, 40)
        self.trace([(M + 51, 13), (M + 51, 53)])
        self.label(self.kicker, M + 63, 16)
        self.text(self.header_title, M + 63, 30, 230, 14, 19, WHITE, True)
        self.trace([(331, 20), (354, 20), (365, 31), (418, 31)])
        self.trace([(331, 46), (354, 46), (365, 36), (418, 36)])
        self.dot(331, 20, 1.6, CYAN)
        self.dot(331, 46, 1.6, GOLD)
        self.badge(428, 20, W - M - 428)
        self.rect(M, 63, 53, 3, CYAN)
        self.label(f"{self.page:02d}  /  {section}", M, 84, BLUE)
        self.footer()

    def title(self, name, description, top=100):
        b = self.text(name, M, top, INNER, 26, 31, INK, True)
        return self.text(description, M, b + 5, INNER, 11, 15.5, SUB) + 12

    def step(self, n, heading, body, x, top, w):
        self.rect(x, top + 1, 24, 24, "#dcebf9", 6)
        self.text(f"{n:02d}", x + 6, top + 6, 15, 9, 12, BLUE, True)
        b = self.text(heading, x + 34, top, w - 34, 13, 17, INK, True)
        return self.text(body, x + 34, b + 3, w - 34, 10.5, 14.5, SUB) + 12

    def note(self, heading, body, x, top, w, tone=BLUE, fill=WHITE):
        # measure first, then draw the box behind the text
        style = ParagraphStyle("m", fontName="UI", fontSize=10.2, leading=14.2)
        hs = ParagraphStyle("h", fontName="UI-Bold", fontSize=11.5, leading=15.5)
        h = Paragraph(heading, hs).wrap(w - 30, H)[1] + 4 + Paragraph(body, style).wrap(w - 30, H)[1] + 20
        self.rect(x, top, w, h, fill, 10, RULE)
        self.rect(x, top + 9, 3, h - 18, tone, 1.5)
        b = self.text(heading, x + 15, top + 10, w - 30, 11.5, 15.5, INK, True)
        self.text(body, x + 15, b + 4, w - 30, 10.2, 14.2, SUB)
        return top + h + 10

    def table(self, rows, widths, x, top, head=True, size=9, status_col=None):
        st = ParagraphStyle("c", fontName="UI", fontSize=size, leading=size + 3.2, textColor=HexColor(INK))
        sh = ParagraphStyle("h", fontName="UI-Bold", fontSize=size, leading=size + 3.2, textColor=HexColor(WHITE))
        data = []
        for r, row in enumerate(rows):
            cells = []
            for ci, v in enumerate(row):
                if r == 0 and head:
                    cells.append(Paragraph(v, sh))
                elif status_col is not None and ci == status_col:
                    color = {"PASS": GREEN, "BUILT": GREEN, "PENDING": AMBER, "FAIL": RED, "SOURCE": BLUE}.get(v.split()[0], INK)
                    cells.append(Paragraph(f'<font name="UI-Bold" color="{color}">{v}</font>', st))
                else:
                    cells.append(Paragraph(v, st))
            data.append(cells)
        t = Table(data, colWidths=widths)
        style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("GRID", (0, 0), (-1, -1), .5, HexColor(RULE)),
                 ("BACKGROUND", (0, 1 if head else 0), (-1, -1), HexColor(WHITE)),
                 ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                 ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
        if head:
            style.append(("BACKGROUND", (0, 0), (-1, 0), HexColor(NAVY)))
        for r in range(1 if head else 0, len(data)):
            if r % 2 == 0:
                style.append(("BACKGROUND", (0, r), (-1, r), HexColor("#f6f9fd")))
        t.setStyle(TableStyle(style))
        _, h = t.wrapOn(self.c, sum(widths), H)
        t.drawOn(self.c, x, H - top - h)
        return top + h + 10

    def check(self, bottom, where):
        assert bottom <= BOTTOM, f"page {self.page}: content runs into the footer at {where} ({bottom:.0f})"

    # ---- cover
    def cover(self, kicker, title, tagline, intro, cards, art, before):
        self.new_page()
        self.c.bookmarkPage("cover")
        self.c.addOutlineEntry("Cover", "cover", level=0)
        self.rect(0, 0, W, H, NAVY)
        # subtle circuit traces in the background
        for pts in ([(0, 300), (40, 300), (60, 280), (60, 140)], [(W, 250), (W - 30, 250), (W - 50, 270), (W - 50, 380)],
                    [(0, 640), (25, 640), (40, 625), (40, 560)], [(W, 700), (W - 26, 700), (W - 40, 686), (W - 40, 610)]):
            self.trace(pts, "#16365a", .8)
        self.rect(M, 34, INNER, 88, "#0d1e33", 14, "#315172")
        self.framed_logo(M + 9, 43, 70)
        self.trace([(M + 93, 49), (M + 93, 103)])
        self.label(kicker, M + 108, 51, CYAN, 8)
        self.text("Prepared by", M + 108, 67, 200, 8.5, 11, "#acc0d6")
        self.text("Anshuva Samanta", M + 108, 79, 233, 19, 24, WHITE, True)
        self.trace([(342, 34), (370, 34), (381, 46), (536, 46), (548, 34)])
        self.trace([(342, 122), (370, 122), (381, 110), (536, 110), (548, 122)])
        self.dot(381, 46, 1.7, CYAN)
        self.dot(536, 110, 1.7, GOLD)
        self.badge(400, 59, 149, True)
        self.text(title, M, 148, INNER, 44, 50, WHITE, True)
        self.text(tagline, M, 206, INNER, 21, 27, GOLD, True)
        self.text(intro, M, 244, INNER, 12.5, 18, "#d9e5f4")
        cw = (INNER - 18) / 3
        for i, (cap, detail, key) in enumerate(cards):
            x = M + i * (cw + 9)
            self.rect(x, 306, cw, 57, "#152c48", 9, "#24496f")
            self.label(cap, x + 12, 316, CYAN, 7.3)
            self.text(detail, x + 12, 334, cw - 24, 12, 16, WHITE, True)
            self.c.linkRect("", key, (x, H - 363, x + cw, H - 306), thickness=0)
        art(self)
        self.rect(M, 641, INNER, 65, "#133349", 11)
        self.dot(M + 20, 662, 4, GOLD)
        self.text(before[0], M + 34, 651, INNER - 54, 12.5, 17, CYAN, True)
        self.text(before[1], M + 34, 673, INNER - 54, 10.5, 15, WHITE)
        self.footer(True)

    def save(self):
        self.c.save()


def cover_art(d):
    """Simplified TV - Wi-Fi - phone illustration (drawn shapes, sample code)."""
    d.rect(M, 380, INNER, 236, "#10233b", 14, "#2f5278")
    d.trace([(M + 1, 422), (83, 422), (107, 397), (155, 397)], "#214a70")
    d.trace([(W - M - 1, 576), (531, 576), (504, 600), (473, 600)], "#214a70")
    d.trace([(159, 604), (204, 604), (223, 586), (360, 586), (385, 604), (443, 604)], "#214a70")
    d.dot(155, 397, 2, CYAN)
    d.dot(473, 600, 2, GOLD)
    d.rect(81, 426, 214, 128, "#101a2c", 11, "#5784a6")
    d.rect(88, 433, 200, 113, "#172b47", 7)
    d.framed_logo(100, 444, 31)
    d.text("TV File Link", 139, 449, 135, 15, 19, WHITE, True)
    d.rect(101, 486, 86, 36, "#102038", 5, "#345a7e")
    d.label("TV CODE", 109, 491, CYAN, 6.2)
    d.text("0 4 2 6 1 5", 109, 503, 75, 11, 13, GOLD, True, "Mono-Bold")
    for i, wdt in enumerate((80, 68, 58)):
        d.rect(197, 488 + 12 * i, wdt, 6, "#3c5572", 3)
    d.trace([(188, 554), (188, 566)], "#5784a6", 2)
    d.rect(158, 564, 60, 3, "#5784a6", 1.5)
    d.trace([(306, 482), (390, 482)], CYAN, 1.6)
    d.trace([(382, 476), (390, 482), (382, 488)], CYAN, 1.6)
    d.trace([(390, 508), (306, 508)], GOLD, 1.6)
    d.trace([(314, 502), (306, 508), (314, 514)], GOLD, 1.6)
    d.label("WI-FI", 329, 456, WHITE, 10)
    d.rect(409, 408, 99, 168, "#0d1729", 14, "#5784a6")
    d.rect(415, 420, 87, 143, "#172b47", 8)
    d.rect(441, 413, 34, 2, "#5784a6", 1)
    d.framed_logo(426, 435, 22)
    d.text("Browser", 426, 465, 67, 11, 14, WHITE, True)
    d.rect(426, 487, 64, 17, "#102038", 5, "#345a7e")
    d.text("042615", 433, 489, 52, 8.5, 11, GOLD, True, "Mono-Bold")
    d.rect(426, 512, 64, 18, GOLD, 5)
    d.text("Connect", 439, 515, 44, 7.6, 11, NAVY, True)
    d.text("Illustration. Code 042615 is a sample value.", M + 14, 596, 260, 7.5, 10, "#7f9bbb")


# ============================================================ test results
RES_DIR = ROOT / "work" / "tests" / "results"


def load_suites():
    """Transfer and file-manager results for each emulator that has them (missing files are skipped)."""
    suites = []
    for stem, title, what in [
        ("emulator-results-api30", "Wi-Fi transfer", "Android 11"),
        ("emulator-results-api28", "Wi-Fi transfer", "Android 9"),
        ("filemanager-api30", "File manager", "Android 11"),
        ("filemanager-api28", "File manager", "Android 9"),
    ]:
        f = RES_DIR / (stem + ".json")
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            env = data["environment"] if isinstance(data["environment"], str) else data["environment"]["emulator"]
            date = data.get("date") or (data["environment"].get("date") if isinstance(data["environment"], dict) else "")
            suites.append({"title": f"{title}: {what} TV emulator", "env": env, "date": date, "results": data["results"]})
    return suites


SUITES = load_suites()
TOTAL_PASS = sum(r["result"] == "PASS" for s in SUITES for r in s["results"])
TOTAL_CHECKS = sum(len(s["results"]) for s in SUITES)


def render_suite(d, suite):
    res = suite["results"]
    passed = sum(r["result"] == "PASS" for r in res)
    pending = sum(r["result"] == "PENDING" for r in res)
    failed = len(res) - passed - pending
    summary = f"{passed} passed, {failed} failed" + (f", {pending} pending" if pending else "") + f" ({suite['date']}, final v1.4.1 APK)."
    y = d.title(suite["title"], summary)
    y = d.note("Where this ran", suite["env"] + " on the Windows build PC. The TV app was driven with D-pad key events; results were checked with adb and, for My files, through the Wi-Fi transfer API (same requests as the browser page). Video and audio playback was checked in Android's media and audio services.", M, y, INNER, BLUE)
    widths = [26, 196, 50, INNER - 272]
    head = ["#", "Check", "Result", "Detail"]

    def detail(r):
        raw = r["detail"]
        if raw.startswith("{"):
            try:
                info = json.loads(raw)
                raw = f"{info.get('connectedStatus', '')} {len(info.get('rows', []))} items listed; code box inputmode={info.get('inputmode')}"
            except ValueError:
                raw = "Chrome connected and listed the files"
        text_ = " ".join(raw.split()).replace("&", "&amp;").replace("<", "&lt;")
        return text_ if len(text_) <= 95 else text_[:92] + "..."

    rows = [[str(i), r["test"], r["result"], detail(r)] for i, r in enumerate(res, 1)]

    def fits(part, top):
        st = ParagraphStyle("c", fontName="UI", fontSize=7.6, leading=10.8)
        t = Table([[Paragraph(c, st) for c in row] for row in [head] + part], colWidths=widths)
        t.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                               ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
        return top + t.wrapOn(d.c, sum(widths), H)[1] + 10 <= BOTTOM - 60

    while rows:
        n = len(rows)
        while n > 1 and not fits(rows[:n], y):
            n -= 1
        y = d.table([head] + rows[:n], widths, M, y, status_col=2, size=7.6)
        d.check(y, "results")
        rows = rows[n:]
        if rows:
            d.new_page("TEST RESULTS", None)
            y = d.title(suite["title"] + " (continued)", summary, 100)
    return y


# ============================================================ USER GUIDE
def user_guide(total=99):
    out = ROOT / "TV File Link - User Guide.pdf"
    d = Doc(out, "TV File Link - User Guide", "Send and receive files between a Fire TV Stick and a browser over Wi-Fi",
            "TV FILE LINK  /  USER GUIDE", "Wi-Fi transfer and file manager", total)
    d.cover("FIRE TV STICK  /  USER GUIDE", "TV File Link", "Wi-Fi transfer and file manager for Fire TV",
            "Send files from a phone, tablet, or computer to your TV, and download them back, using only a web browser on the same Wi-Fi network. No extra app is needed on the other device.",
            [("START TRANSFER", "On your Fire TV", "start"), ("CONNECT", "With a six-digit code", "connect"),
             ("SEND AND RECEIVE", "In your browser", "use")], cover_art,
            ("Before you start", "Install TV File Link on the Stick and keep your phone, tablet, or computer on the same Wi-Fi network."))

    # 2 - The app on the TV
    d.new_page("THE APP ON YOUR TV", "start")
    y = d.title("Start Wi-Fi Transfer on the TV", "TV File Link has two areas: Wi-Fi Transfer on the left and My files on the right.")
    half = (INNER - 18) / 2
    a = d.step(1, "Join the same Wi-Fi", "Connect the Fire TV Stick and your other device to the same Wi-Fi network (or the Stick by Ethernet on the same router).", M, y, half)
    b = d.step(2, "Select Start transfer", "Open TV File Link. Focus starts on <b>Start transfer</b>; press the center (Select) button on the remote.", M + half + 18, y, half)
    y = max(a, b)
    e = d.pic("tv-transfer-files-emulator.png", M, y + 2, INNER)
    y = d.text("<b>TV screen with an active transfer.</b> Captured from TV File Link running on the Android TV emulator (not a physical Fire TV). The address and code are sample values; your TV shows its own.",
               M, e + 8, INNER, 8.8, 12.5, SUB) + 10
    y = d.note("What the TV shows", "<b>Transfer active</b>, the full browser address with <b>http://</b> and the port number after the colon, and a fresh <b>six-digit code</b>. The code changes every time you start a transfer and can begin with 0, so read all six digits.", M, y, INNER, GREEN, "#e0f3ef")
    d.check(y, "tv page")

    # 3 - Connect
    d.new_page("CONNECT", "connect")
    y = d.title("Connect from a phone, tablet, or computer", "Use any modern browser. Type the address exactly as the TV shows it.")
    left = 262
    ix = M + left + 22
    iw = W - M - ix
    s = d.step(1, "Type the full address", "Open Chrome, Safari, Edge, or Firefox. In the <b>address bar</b> (not a search box) type the address from the TV, including <b>http://</b> and the <b>:port</b>.", M, y, left)
    s = d.rect(M + 34, s - 4, left - 34, 26, "#102038", 6) or s
    d.text("http://192.168.1.42:50813", M + 44, s + 2, left - 50, 11, 14, GOLD, True, "Mono-Bold")
    d.text("Sample address. Use the one on your TV.", M + 34, s + 26, left - 34, 8.5, 11, SUB)
    s += 48
    s = d.step(2, "Enter the six-digit code", "Type all six digits, including any leading zero (for example <b>042615</b>). Phones show a number keypad for this box.", M, s, left)
    s = d.step(3, "Select Connect", "The page opens <b>My files</b>, the TV File Link library on the TV.", M, s, left)
    e = d.pic("phone-enter-access-code-crop.png", ix, y, iw, max_h=330)
    d.text("Code-entry screen in Chrome (phone size). The code shown is a sample value.", ix, e + 6, iw, 8.5, 11.5, SUB)
    y = max(s, e + 40)
    y = d.note("The code only works for this session", "When the TV stops the transfer, the code and the browser connection end. Start transfer again to get a new code.", M, y, INNER, BLUE)
    d.check(y, "connect page")

    # 4 - Send and receive
    d.new_page("SEND AND RECEIVE", "use")
    y = d.title("Upload and download files", "After you connect, the browser shows the folder you are in, an upload box, and the file list.")
    s = d.step(1, "Choose the folder", "Select a folder name to open it. Use <b>Up one folder</b> to go back. Uploads go to the folder you are viewing.", M, y, left)
    s = d.step(2, "Upload one or more files", "Select <b>Choose Files</b>, pick one or several files, then <b>Upload</b>. A bar shows progress, for example <i>File 2 of 5 (40%)</i>. Wait for <b>Upload complete</b>.", M, s, left)
    s = d.step(3, "Download from the TV", "Select <b>Download</b> next to a file to save it on your phone or computer.", M, s, left)
    s = d.step(4, "See it on the TV", "While transfer is active, the TV list updates by itself within a few seconds. <b>Refresh</b> also works.", M, s, left)
    e = d.pic("phone-transfer-page.png", ix, y, iw, max_h=430)
    d.text("Connected browser page in Chrome with sample files (phone size).", ix, e + 6, iw, 8.5, 11.5, SUB)
    y = max(s, e + 40)
    y = d.note("Limits", "Each file can be up to just under 2 GiB, and the TV needs enough free storage. Keep the browser page and the TV app open until the upload finishes.", M, y, INNER, AMBER, "#fdf3e4")
    d.check(y, "send page")

    # 5 - File manager: locations and access
    d.new_page("FILE MANAGER", "files")
    y = d.title("Browse your TV storage", "The right side of the screen is a file manager. The tabs at the top choose where you are.")
    rows = [["Tab", "What it shows"],
            ["<b>My files</b>", "TV File Link's own library. Files sent from a browser arrive here, and the browser can only see this location."],
            ["<b>Internal storage</b>", "The Stick's shared storage: Download, Movies, Pictures, Music and so on. Fire OS only."],
            ["<b>USB drive</b> (one tab per drive)", "A USB stick or drive connected through an OTG adapter, or an SD card. Appears by itself when it is plugged in and disappears when it is removed; free space is shown next to the folder name. Fire OS only. On Fire OS 6 and 7 drives are <b>read-only</b>: you can open files and copy them to My files or Internal storage."]]
    y = d.table(rows, [150, INNER - 150], M, y, size=9.5)
    y = d.text("<b>First time: allow storage access</b> (needed for Internal storage and USB, not for My files)", M, y + 2, INNER, 11.5, 15) + 4
    rows = [["Your Fire TV", "What happens after you select Allow storage access"],
            ["Fire OS 6 or 7", "A permission prompt appears. Select <b>Allow</b>."],
            ["Fire OS 8", "Settings opens. Turn on <b>Allow access to manage all files</b>, or open Permissions &gt; Storage and choose <b>All files</b>, then press <b>Back</b> to return."]]
    y = d.table(rows, [110, INNER - 110], M, y, size=9.5)
    if (SHOTS / "fm-internal-storage-emulator.png").exists():
        e = d.pic("fm-internal-storage-emulator.png", M + 40, y + 2, INNER - 80, max_h=250)
        y = d.text("Internal storage tab with the test folder. Captured from v1.4.1 on the Android TV emulator; names, sizes and dates are sample values.",
                   M + 40, e + 6, INNER - 80, 8.5, 11.5, SUB) + 8
    d.check(y, "file manager page")

    # 6 - Operations
    d.new_page("FILE MANAGER", None)
    y = d.title("Copy, move and organize", "Move to an item and press Select to open it. Press <b>Options</b> (or the Menu key on the remote) for everything else.")
    rows = [["Task", "On the remote"],
            ["Open a folder or file", "Move to it and press Select. <b>Back</b> goes up one folder; at the top of a drive it returns to My files."],
            ["Copy or move", "<b>Options</b> &gt; <b>Copy</b> (or <b>Move</b>). Open the destination, in any tab or folder, then select <b>Paste</b> (or <b>Move here</b>) in the button row. A progress window shows the amount copied and has <b>Cancel</b>."],
            ["Copy to My files", "<b>Options</b> &gt; <b>Copy to My files</b>: one step, handy before downloading a file to a phone."],
            ["Same name already there", "The copy gets a new name such as <i>photo (1).png</i>. Nothing is overwritten."],
            ["New folder", "Select <b>New folder</b>, type a name, press <b>Back</b> to close the keyboard, move to <b>Save</b>, press Select."],
            ["Rename", "<b>Options</b> &gt; <b>Rename</b>, type the new name, <b>Save</b>."],
            ["Delete", "<b>Options</b> &gt; <b>Delete</b>, then confirm. For a folder, the message says how many items inside will also be deleted."],
            ["Details", "<b>Options</b> &gt; <b>Details</b>: type, size (folders: total size and number of items), date and location."],
            ["Sort", "Select <b>Sort</b> to switch between name, date (newest first) and size (largest first). Folders stay on top."]]
    y = d.table(rows, [128, INNER - 128], M, y, size=9.3)
    shot = "fm-usb-drive-emulator.png" if (SHOTS / "fm-usb-drive-emulator.png").exists() else "tv-delete-confirm-emulator.png"
    if (SHOTS / shot).exists():
        e = d.pic(shot, M + 70, y + 2, INNER - 140, max_h=215)
        cap = ("A USB drive tab after pasting a file. Captured on the Android TV emulator using its virtual USB disk; sample values."
               if shot.startswith("fm-usb") else "Delete confirmation on the TV. Captured on the Android TV emulator; sample values.")
        y = d.text(cap, M + 70, e + 6, INNER - 140, 8.5, 11.5, SUB) + 8
    d.check(y, "operations page")

    # 7 - Viewers
    d.new_page("FILE MANAGER", None)
    y = d.title("Watch, listen and read", "Pictures, videos, music and text files open full screen inside TV File Link.")
    rows = [["File type", "Remote keys"],
            ["Pictures (JPG, PNG, GIF, WebP ...)", "<b>Left / Right</b>: previous / next picture in the folder. <b>Back</b>: close."],
            ["Video and music (MP4, MKV, WebM, MP3, AAC, WAV ...)", "<b>Select</b> or Play/Pause: pause and resume. <b>Left / Right</b>: back or forward 10 seconds. <b>Back</b>: stop and close."],
            ["Text (TXT, LOG, CSV, JSON, SRT ...)", "<b>Up / Down</b>: scroll. Large files show the first 512 KB."],
            ["Anything else", "<b>Options</b> &gt; <b>Open with another app</b> if an app on the TV can open it; otherwise copy it to My files and download it to another device."]]
    y = d.table(rows, [175, INNER - 175], M, y, size=9.4)
    if (SHOTS / "fm-image-viewer-emulator.png").exists():
        e = d.pic("fm-image-viewer-emulator.png", M + 50, y + 2, INNER - 100, max_h=255)
        y = d.text("Picture viewer with the caption showing the position in the folder. Captured on the Android TV emulator; the picture is a test image.",
                   M + 50, e + 6, INNER - 100, 8.5, 11.5, SUB) + 8
    y = d.note("Playback depends on the TV", "Video and music use the Fire TV's own decoders. If a file shows <i>this format cannot be played here</i>, try <b>Open with another app</b>. On Vega OS, picture and text viewing works inside My files; video and music playback is not available yet.", M, y, INNER, AMBER, "#fdf3e4")
    d.check(y, "viewers page")

    # 6 - Stop and privacy
    d.new_page("STOP AND STAY SAFE", "stop")
    y = d.title("Stop the transfer", "Close the session as soon as you are done.")
    y = d.step(1, "Select Stop transfer", "On the TV, select <b>Stop transfer</b>. The address stops working and the browser shows that the session ended.", M, y, INNER)
    y = d.step(2, "Leaving the app also stops it", "Pressing <b>Home</b> or switching apps closes the transfer automatically. Reopen TV File Link and select Start transfer to share again.", M, y, INNER)
    y = d.note("How the connection is protected", "Only devices that enter the current code can see or change files. Each browser receives its own session key tied to that device's network address. After 3 wrong codes in a row the TV makes the browser wait (1, 2, 4 ... up to 60 seconds), and it allows at most 10 wrong codes per minute from one device. Files can only be read or written inside the TV File Link library.", M, y, INNER, GREEN, "#e0f3ef")
    y = d.note("Use a trusted network", "Transfers stay on your local network and use plain HTTP, like most TV file-sharing apps. Use them on your home Wi-Fi, not on public or hotel networks.", M, y, INNER, AMBER, "#fdf3e4")
    d.check(y, "stop page")

    # 7-8 - Troubleshooting
    d.new_page("TROUBLESHOOTING", "help")
    y = d.title("If something does not work", "Find the message or symptom, then try the fix.")
    rows = [["Symptom or message", "What to do"],
            ["The page does not load", "Check that transfer is active on the TV and both devices use the same Wi-Fi. Type the full address with <b>http://</b> and the port into the address bar. Turn off a VPN on the phone or computer. Guest networks and 'AP isolation' block devices from seeing each other; use the main network."],
            ["The browser changes http to https", "Type <b>http://</b> explicitly. If the browser forces HTTPS, try another browser."],
            ["That code is not correct", "Read all six digits on the TV again, including a leading 0. The code changes each time transfer starts."],
            ["Too many wrong codes. Wait N seconds", "Wait the time shown, then enter the current code."],
            ["Too many attempts. Wait a minute", "Wait one minute. This limit protects the TV from guessing."],
            ["This transfer session has ended", "Transfer was stopped or the app was closed. Start transfer on the TV and enter the new code."],
            ["\"name\" already exists in this folder", "A file with the same name is already there. Rename the file on your device, or delete or rename the TV copy, then upload again."],
            ["Could not save the file. Check free space.", "The TV storage is full or unavailable. Delete files you no longer need and try again."],
            ["The upload limit is 2 GiB per file", "Split or compress the file, or copy it another way."],
            ["Connection to the TV was lost", "The Wi-Fi dropped or the TV app closed. Reconnect and upload the remaining files."],
            ["Too many devices are connected", "Up to 8 browsers can connect per session. Stop and restart transfer on the TV."],
            ["Connect your Fire TV to Wi-Fi or Ethernet first", "The Stick has no network. Check Settings &gt; Network on the TV."]]
    y = d.table(rows, [180, INNER - 180], M, y, size=9.2)
    d.check(y, "help page")
    d.new_page("TROUBLESHOOTING", None)
    y = d.title("More help", "Common questions about files and versions.", 100)
    rows = [["Question", "Answer"],
            ["Where are the files stored?", "In the app's private library on the TV (My files). Other apps cannot see them, and they are removed if TV File Link is uninstalled. Download anything you want to keep before uninstalling."],
            ["Do I keep my files when I update?", "Yes. Version 1.4.1 installs over 1.2, 1.3 and 1.4 and keeps My files. This was checked on the Android TV emulator."],
            ["Does it use the internet?", "No. The phone or computer connects straight to the TV on your local network."],
            ["Can two phones connect at once?", "Yes, each device enters the code and gets its own session, up to 8 per session."],
            ["Can the browser see my USB drive or Downloads?", "No. The browser only sees My files. To send a file elsewhere, copy or move it on the TV with the file manager."],
            ["Which TV OS does this guide cover?", "Fire OS (APK) has everything in this guide. Vega OS (VPKG) has the transfer and a file manager for My files only, because Vega apps cannot reach shared storage or USB drives. See the Installation and Testing Guide for test status."]]
    y = d.table(rows, [170, INNER - 170], M, y, size=9.4)
    rows = [["File manager problem", "What to do"],
            ["Only My files is shown", "Internal storage and USB tabs are Fire OS only. On Fire OS, a drive tab appears when the drive is plugged in; select Refresh if it does not."],
            ["Allow storage access does nothing", "Open Settings &gt; Applications &gt; Manage Installed Applications &gt; TV File Link &gt; Permissions and allow Storage (All files), then return to the app."],
            ["USB drive not shown", "Use a drive formatted FAT32 or exFAT and an OTG adapter. Select Refresh. Drives set up as internal storage appear inside Internal storage."],
            ["Not enough free space", "The copy did not start. Delete files or choose another drive."],
            ["USB drive says Read-only", "Fire OS 6 and 7 do not let apps change USB drives. Copy the files to My files or Internal storage instead. Fire OS 8 can write to drives."]]
    y = d.table(rows, [170, INNER - 170], M, y + 2, size=9.2)
    y = d.note("Sample values in this guide", "The address http://192.168.1.42:50813 and the code 042615 are examples. Screenshots come from emulator test sessions, so their addresses (starting with 10.0.2.), codes and file names are sample values too. Always use the address and code on your own TV.", M, y + 4, INNER, BLUE)
    d.check(y, "more help")
    d.save()
    return out, d.page


# ============================================================ INSTALLATION AND TESTING GUIDE
def install_guide(total=99):
    out = ROOT / "TV File Link - Installation and Testing Guide.pdf"
    d = Doc(out, "TV File Link - Installation and Testing Guide", "Packages, installation, first-run checks and test results for TV File Link",
            "TV FILE LINK  /  INSTALL AND TEST", "Installation and testing", total)
    d.cover("FIRE OS + VEGA OS  /  INSTALL AND TEST", "TV File Link", "Installation and Testing Guide",
            "Which package belongs to which Fire TV operating system, how to install each build, what to check on first run, and what has been tested so far.",
            [("PACKAGES", "Fire OS APK, Vega VPKG", "packages"), ("INSTALL", "Step by step", "fireos"),
             ("TEST RESULTS", f"{TOTAL_PASS} of {TOTAL_CHECKS} checks passed", "results")], cover_art,
            ("Status at a glance", "Fire OS APK v1.4.1 (transfer + file manager): built, signed and tested on Android 11 and Android 9 TV emulators; physical Fire TV test pending. Vega OS: source ready; VPKG build and device test pending."))

    # 2 - packages
    d.new_page("WHICH PACKAGE", "packages")
    y = d.title("Pick the package for your Stick", "Check the OS under Settings > My Fire TV (or Device & Software) > About on the TV.")
    rows = [["TV operating system", "Package", "Status"],
            ["<b>Fire OS</b> 6, 7 or 8 (Android-based Fire TV Sticks and Fire TV devices)", "fire-os/TV-File-Link-Fire-OS.apk", "BUILT  signed APK, v1.4.1"],
            ["<b>Vega OS</b> (Fire TV devices that run Amazon's Vega OS)", "vega-os/build/*.vpkg (to be produced)", "PENDING  source only"]]
    y = d.table(rows, [205, 175, INNER - 380], M, y, status_col=2, size=9.4)
    y = d.text("<b>Fire OS APK facts</b> (verified with apksigner and aapt2 on the build PC)", M, y + 4, INNER, 12, 16, INK) + 6
    apk = ROOT / "fire-os" / "TV-File-Link-Fire-OS.apk"
    import hashlib
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    rows = [["Item", "Value"],
            ["App ID", "com.anshuva.tvfilelink (unchanged from v1.2)"],
            ["Version", "1.4.1 (versionCode 6). Earlier: 1.4 (versionCode 5), 1.3 (versionCode 4), 1.2 (versionCode 3)"],
            ["Minimum OS", "Android 7.0 / API 24 (Fire OS 6 and newer); target API 34"],
            ["Permissions", "Internet, network state, storage (READ/WRITE_EXTERNAL_STORAGE up to Android 9/10, MANAGE_EXTERNAL_STORAGE on Android 11) for the file manager"],
            ["Signing", "APK Signature Scheme v2 and v3. Certificate CN=TV File Link Sideload, SHA-256 237eabf4 4bc7c3a0 78b1eb8a 74ba9228 4313b3d6 a987f247 131d4c1c d4ac8ccf (same key as v1.2, so it updates in place)"],
            ["Native code", "armeabi-v7a (32-bit ARM) and arm64-v8a (64-bit ARM) for Fire TV hardware; x86 and x86_64 for emulators only"],
            ["File size", f"{apk.stat().st_size:,} bytes"],
            ["APK SHA-256", " ".join(digest[i:i + 8] for i in range(0, 64, 8))]]
    y = d.table(rows, [95, INNER - 95], M, y, size=9)
    y = d.note("Built packages, source and previews", "<b>Built:</b> the Fire OS APK above. <b>Source only:</b> the Vega OS app (vega-os folder), whose TypeScript passes type checking and whose JavaScript bundle builds; its native module and VPKG need the Vega SDK. <b>Screens in the guides:</b> real captures from the emulator and Chrome, not layout previews.", M, y, INNER, BLUE)
    d.check(y, "packages")

    # 3 - Fire OS install
    d.new_page("INSTALL ON FIRE OS", "fireos")
    y = d.title("Install the Fire OS APK", "Sideload with ADB from a computer on the same network. An update keeps My files.")
    y = d.text("<b>Prerequisites</b>", M, y, INNER, 12, 16) + 4
    for item in ["A computer with Android SDK Platform-Tools (adb) on the same network as the Stick.",
                 "On the TV: Settings &gt; My Fire TV &gt; About, select the device name 7 times to show Developer Options (newer Fire OS), then turn on <b>ADB debugging</b>.",
                 "The Stick's IP address from Settings &gt; My Fire TV &gt; About &gt; Network."]:
        y = d.text("&bull;&nbsp; " + item, M + 8, y, INNER - 8, 10.3, 14.5, SUB) + 3
    y += 6
    y = d.step(1, "Connect to the Stick", "Run the command below. Accept the <b>Allow USB debugging</b> prompt on the TV the first time.", M, y, INNER)
    for cmd in ["adb connect FIRE_TV_IP:5555", 'adb install -r "TV-File-Link-Fire-OS.apk"', "adb shell am start -n com.anshuva.tvfilelink/.MainActivity"]:
        d.rect(M + 34, y - 6, INNER - 34, 22, "#102038", 5)
        d.text(cmd, M + 44, y - 1, INNER - 50, 10, 13, GOLD, False, "Mono")
        y += 26
    y = d.text("Replace FIRE_TV_IP with the Stick's address. <b>-r</b> replaces an installed copy and keeps its files.", M + 34, y, INNER - 34, 9.5, 13, SUB) + 12
    y = d.step(2, "Open the app", "TV File Link appears in Your Apps &amp; Channels with the AS banner. You can also use the third command above.", M, y, INNER)
    y = d.note("Update from v1.2, v1.3 or v1.4", "v1.4.1 uses the same app ID and signing key, so <b>adb install -r</b> installs it over v1.2, v1.3 or v1.4 and keeps everything in My files. If Android reports INSTALL_FAILED_UPDATE_INCOMPATIBLE, the installed copy was signed with a different key; download your files first, then uninstall it and install v1.4.1.", M, y, INNER, GREEN, "#e0f3ef")
    y = d.text("<b>Amazon documentation</b>", M, y, INNER, 11.5, 15) + 3
    y = d.link("Connect to Fire TV through ADB", LINKS["adb"], M, y, INNER) + 2
    y = d.link("Install and run your app (Fire TV)", LINKS["install"], M, y, INNER)
    d.check(y, "fire os install")

    # 3b - file manager setup
    d.new_page("SET UP THE FILE MANAGER", "fmsetup")
    y = d.title("Storage access for the file manager", "My files works right away. Internal storage and USB drives need one permission, which differs by Fire OS version.")
    rows = [["Fire OS (Android)", "On the TV", "From a computer with ADB (testers)"],
            ["Fire OS 6 (7.1) and 7 (9)", "Select a storage tab, then <b>Allow storage access</b>, then <b>Allow</b> in the prompt.",
             "adb shell pm grant com.anshuva.tvfilelink android.permission.READ_EXTERNAL_STORAGE (and WRITE_EXTERNAL_STORAGE)"],
            ["Fire OS 8 (10 / 11)", "<b>Allow storage access</b> opens Settings: turn on <b>all files</b> access (or Permissions &gt; Storage &gt; <b>All files</b>), then press Back.",
             "adb shell appops set com.anshuva.tvfilelink MANAGE_EXTERNAL_STORAGE allow"]]
    y = d.table(rows, [100, 180, INNER - 280], M, y, size=9)
    y = d.note("If Settings does not open the right screen", "Some TV builds lack the direct <i>all files access</i> screen. The app then opens the general list or the app's own settings page. Path by hand: Settings &gt; Applications &gt; Manage Installed Applications &gt; TV File Link &gt; Permissions &gt; Storage.", M, y, INNER, BLUE)
    rows = [["USB drives", "Detail"],
            ["Connection", "Fire TV Sticks need a USB OTG adapter (micro-USB or USB-C, depending on the model). Fire TV Cube and some TVs have a USB port."],
            ["Format", "FAT32 or exFAT. A drive set up as <i>internal storage</i> becomes part of Internal storage instead of its own tab."],
            ["Writing", "Fire OS 8: read and write. Fire OS 6/7: read-only (an Android 7-9 rule for apps); the tab says so and offers Copy only."],
            ["Detection", "Plug in the drive: a tab with its name appears by itself (Refresh also works). If the open drive is removed, the app returns to My files and says so."]]
    y = d.table(rows, [80, INNER - 80], M, y, size=9.2)
    y = d.note("Browser transfer stays limited to My files", "Granting storage access does <b>not</b> expose Internal storage or USB drives on the network. Phones and computers that connect with the code still see only My files.", M, y, INNER, GREEN, "#e0f3ef")
    d.check(y, "fm setup")

    # 4 - Vega
    d.new_page("BUILD AND INSTALL ON VEGA OS", "vega")
    y = d.title("Build the Vega OS VPKG", "The Vega build must run on macOS or Ubuntu with Amazon's Vega SDK. Windows and WSL are not supported by Amazon.")
    rows = [["Requirement", "Detail"],
            ["Build host", "Ubuntu 20.04 or newer (x86_64), or macOS (Apple silicon; Intel Macs supported only up to SDK 0.24). About 20 GB free disk space."],
            ["Tools", "Vega SDK and CLI (match the SDK to your Stick's Vega OS version), Node.js 22.14 or newer, a C++ toolchain, Watchman."],
            ["Project files", "Copy both the <b>vega-os</b> and <b>shared</b> folders; the build copies the transfer server from shared."],
            ["Device", "A Fire TV running Vega OS with developer mode, registered with the Vega CLI."]]
    y = d.table(rows, [100, INNER - 100], M, y, size=9.3)
    y = d.step(1, "Build", "In a terminal with the Vega SDK active:", M, y, INNER)
    for cmd in ["cd vega-os", "npm ci", "npm run build"]:
        d.rect(M + 34, y - 6, INNER - 34, 20, "#102038", 5)
        d.text(cmd, M + 44, y - 2, INNER - 50, 10, 13, GOLD, False, "Mono")
        y += 23
    y = d.text("The script generates the browser page, builds the native transfer module and packages the app. The VPKG appears under <b>vega-os/build/</b>; pick the one whose architecture matches your Stick. Copy it back into the project's vega-os folder.", M + 34, y + 2, INNER - 34, 10, 14, SUB) + 10
    y = d.step(2, "Install and run", "Install the VPKG on the Stick with the Vega CLI as described in Amazon's run-app guide, then open TV File Link and run the first-run checks on page 5.", M, y, INNER)
    y = d.note("Incoming connections still need proof on a Vega Stick", "The Vega app runs the same local web server as Fire OS. Amazon's documentation does not describe a privilege for accepting incoming connections, so it must be confirmed on a real Vega Stick. If Vega blocks them, the smallest working alternative is a relay: TV and browser both connect out to a small server, which passes the code check and the files. That needs internet access (or a computer on the network running the relay), so files would no longer stay purely between the two devices.", M, y, INNER, AMBER, "#fdf3e4")
    y = d.text("<b>Amazon documentation</b>", M, y, INNER, 11.5, 15) + 3
    pairs = [("Install the Vega developer tools", "vega_sdk"), ("Build your app (Vega)", "vega_build"),
             ("Run your app on a Vega device", "vega_run"), ("Vega app manifest overview", "vega_manifest")]
    col = INNER / 2
    for i in range(0, len(pairs), 2):
        b1 = d.link(pairs[i][0], LINKS[pairs[i][1]], M, y, col - 10)
        b2 = d.link(pairs[i + 1][0], LINKS[pairs[i + 1][1]], M + col, y, col - 10)
        y = max(b1, b2) + 2
    d.check(y, "vega")

    # 5 - first run checks
    d.new_page("FIRST-RUN CHECKS", "checks")
    y = d.title("Check the app after installing", "Run these on the TV with a phone or computer on the same Wi-Fi. They take about five minutes.")
    rows = [["#", "Check", "Expected result"],
            ["1", "Open TV File Link", "App logo and title; focus on <b>Start transfer</b>; My files lists the library (files from v1.2 still there after an update)."],
            ["2", "Move with the D-pad", "Focus moves between Start transfer, Up, New folder, Refresh and each file's Options, with a clear gold highlight."],
            ["3", "Start transfer", "Address with http:// and port, plus a six-digit code (leading zeros shown)."],
            ["4", "Open the address on the phone", "TV File Link page with the app logo; number keypad for the code."],
            ["5", "Enter a wrong code", "<i>That code is not correct.</i> After 3 wrong codes: a short wait message."],
            ["6", "Enter the right code", "<i>Connected to your TV.</i> and the file list."],
            ["7", "Upload two files", "Progress bar, <i>Upload complete</i>, files appear on the TV within a few seconds."],
            ["8", "Upload the same file again", "<i>\"name\" already exists in this folder ...</i>"],
            ["9", "Download a file", "The downloaded file opens and matches the original."],
            ["10", "New folder, rename, delete on the TV", "Works with the remote; deleting a folder with files asks first and shows the item count."],
            ["11", "Stop transfer, then Home", "Browser shows the session ended; the address no longer opens."],
            ["12", "Internal storage tab", "Allow storage access (page 4), then Download, Movies ... are listed with free space."],
            ["13", "Open a picture, a video, a song, a text file", "Viewers open full screen; Left/Right, Select and Back work as described in the User Guide."],
            ["14", "Copy a file to My files, then Move one back", "Paste / Move here works; the moved original is gone; the copy can be downloaded in the browser."],
            ["15", "Plug in a USB drive, then unplug it", "A drive tab appears by itself; a pasted file is on the drive; unplugging returns the app to My files."]]
    y = d.table(rows, [22, 150, INNER - 172], M, y, size=9)
    d.check(y, "checks")

    # results: one section per test suite and emulator
    for i, suite in enumerate(SUITES):
        d.new_page("TEST RESULTS", "results" if i == 0 else None)
        y = render_suite(d, suite)
    y = d.note("Also verified on the build PC", "APK signature (v2 and v3) and certificate identical to v1.2; versionCode 6 / versionName 1.4.1; zipalign; ARM 32-bit and 64-bit libraries present. Vega app: TypeScript type check and JavaScript bundle (react-native bundle) succeed; the shared C++ with the new file actions compiles for ARM64.", M, y, INNER, GREEN, "#e0f3ef")
    d.check(y, "results note")

    # 8 - pending
    d.new_page("PENDING TESTS", "pending")
    y = d.title("What still needs a real device", "These checks could not run on the build PC. Each row says what is needed to finish it.")
    rows = [["Test", "Status", "What is needed"],
            ["Fire OS on a physical Fire TV Stick (ARM): install, update, remote navigation, transfer, file manager", "PENDING", "A Fire TV Stick with ADB debugging on, and a computer on the same network. Run the first-run checks."],
            ["Fire OS 8 All files access screen on a real Fire TV", "PENDING", "Fire OS 8 device: check which settings screen Allow storage access opens and that All files can be chosen."],
            ["Writing to USB drives on Fire OS 6/7", "PENDING", "Needs a Storage Access Framework folder grant in the app (follow-up); today these drives are read-only by design."],
            ["Real USB drive on a Stick (OTG adapter)", "PENDING", "The emulator used Android's virtual USB disk. Test a FAT32 / exFAT stick: tab appears, copy and move to and from it, unplug while open."],
            ["Video formats on Fire TV hardware (MKV, HEVC, 4K)", "PENDING", "Play sample files on the Stick; the emulator tested H.264 MP4 and WAV only."],
            ["Transfer between two separate devices on real Wi-Fi", "PENDING", "The Stick plus a phone on the same home Wi-Fi. The emulator test used one PC for both sides."],
            ["Session key tied to each device's address", "PENDING", "Two phones: phone A's download link must be refused on phone B. The emulator shows every client from one address."],
            ["Number keypad on real phones (iPhone and Android)", "PENDING", "Tap the code box on each phone. Checked in Chrome: inputmode=numeric."],
            ["Storage full message on the TV", "PENDING", "A nearly full Stick; upload or copy a file larger than the free space."],
            ["Vega OS VPKG build and device test (transfer, incoming connections, library file manager)", "PENDING", "An Ubuntu or macOS host with the Vega SDK and a Fire TV running Vega OS in developer mode (see docs/VEGA-BUILD.md)."]]
    y = d.table(rows, [170, 56, INNER - 226], M, y, status_col=1, size=8.4)
    y = d.note("Known limitation", "The bundled HTTP library (cpp-httplib) warns that it does not officially support 32-bit builds. Most Fire TV Sticks run 32-bit ARM. The 32-bit x86 emulator passed all checks, including a 6 MB transfer, so a 32-bit ARM Stick test with a large file (over 1 GB) should be part of the physical test.", M, y, INNER, AMBER, "#fdf3e4")
    d.check(y, "pending")
    d.save()
    return out, d.page


def verify(path, pages, phrases, links):
    r = PdfReader(str(path))
    assert len(r.pages) == pages, (path.name, len(r.pages))
    for i, page in enumerate(r.pages, 1):
        content = " ".join((page.extract_text() or "").split())
        assert "Prepared by Anshuva Samanta" in content, (path.name, i)
        assert f"{i:02d} / {pages:02d}" in content, (path.name, i)
    allt = " ".join(" ".join((p.extract_text() or "").split()) for p in r.pages)
    for ph in phrases:
        assert ph in allt, (path.name, ph)
    uris = [a.get_object()["/A"].get("/URI") for p in r.pages for a in p.get("/Annots", []) if "/A" in a.get_object()]
    for u in links:
        assert u in uris, (path.name, u)
    print(f"{path.name}: {pages} pages, {len([u for u in uris if u])} web links, checks OK")


if __name__ == "__main__":
    # two passes: the first counts the pages so every footer shows the right total
    ug, n_ug = user_guide(user_guide()[1])
    ig, n_ig = install_guide(install_guide()[1])
    verify(ug, n_ug, ["Start transfer", "leading zero", "http://", "Upload complete", "Stop transfer", "Copy, move and organize"], [])
    verify(ig, n_ig, ["TV-File-Link-Fire-OS.apk", "PENDING", "adb install -r"], list(LINKS.values())[:6])
