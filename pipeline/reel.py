#!/usr/bin/env python3
"""saiditatwork reel renderer, design C (red top panel, green panel wipes up).

usage:
  reel.py sheet  BANK IDS OUT.png      final frames of the given ids on one sheet
  reel.py still  BANK ID T OUT.png     one full-size frame at time T
  reel.py render BANK IDS OUTDIR       one mp4 per id, with sound
IDS is a comma-separated list such as 001,046,067.

Needs: python3 with Pillow, ffmpeg, the Poppins fonts (Bold, Medium).
"""
import math, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
HANDLE = "saiditatwork"
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-%s.ttf"
RED, GREEN, DARK, WHITE = (222, 64, 70), (26, 146, 98), (22, 22, 26), (255, 255, 255)
SAFE_BOTTOM = 1450          # captions and buttons cover what is below this
REVEAL = (1.3, 1.85)        # seconds: the green panel wipes up

# serie -> (top label, bottom label, teaser, top icon, quote top, quote bottom)
SERIES = {
    "A": ("THOUGHT IT", "SAID IT AT WORK", "AND AT WORK?", "x", True, True),
    "B": ("THE MOMENT", "SAID IT AT WORK", "WORD FOR WORD", "!", False, True),
    "C": ("DON’T SAY", "SAY INSTEAD", "SAY THIS INSTEAD", "x", True, True),
    "D": ("DON’T WRITE", "WRITE INSTEAD", "WRITE THIS INSTEAD", "x", True, True),
    "E": ("THE GOAL", "SAID IT AT WORK", "5 PHRASES", "!", False, False),
    "F": ("WHEN THEY", "SAID IT AT WORK", "AND YOU SAY?", "!", False, True),
    "G": ("BOSS SAID", "BOSS MEANT", "TRANSLATION", "?", True, False),
}
_fonts = {}


def F(weight, size):
    if (weight, size) not in _fonts:
        _fonts[(weight, size)] = ImageFont.truetype(FONT % weight, size)
    return _fonts[(weight, size)]


def clamp(x):
    return max(0.0, min(1.0, x))


def prog(t, a, b):
    return clamp((t - a) / (b - a))


def ease(p):
    return 1 - (1 - p) ** 3


def mix(c1, c2, p):
    return tuple(int(round(a + (b - a) * p)) for a, b in zip(c1, c2))


def typo(s):
    """Straight quotes to typographic ones."""
    s = s.replace("'", "’")
    out, open_ = [], True
    for ch in s:
        if ch == '"':
            out.append("“" if open_ else "”")
            open_ = not open_
        else:
            out.append(ch)
    return "".join(out)


def load_bank(path):
    bank = {}
    for line in open(path, encoding="utf-8"):
        if re.match(r"^\d{3}\|", line):
            i, ser, top, bottom = line.rstrip("\n").split("|")
            bank[i] = {"id": i, "series": ser, "top": top, "bottom": bottom}
    return bank


def layout(d, text, font, max_w, line_h):
    """Word positions (word, x, y, w); '\\n' forces a new line. Returns words, line count."""
    space = d.textlength(" ", font=font)
    out, line = [], 0
    for pi, para in enumerate(text.split("\n")):
        if pi:
            line += 1
        x = 0.0
        for w in para.split(" "):
            ww = d.textlength(w, font=font)
            if x > 0 and x + ww > max_w:
                line += 1
                x = 0.0
            out.append((w, x, line * line_h, ww))
            x += ww + space
    return out, line + 1


def fit(d, text, weight, sizes, ratio, max_w, max_h):
    """Largest size whose wrapped text fits max_h."""
    for size in sizes:
        font, lh = F(weight, size), int(round(size * ratio))
        words, n = layout(d, text, font, max_w, lh)
        if n * lh <= max_h and all(ww <= max_w for _, _, _, ww in words):
            return font, lh, words, n, True
    return font, lh, words, n, False


def tracked(d, xy, text, font, fill, tracking=4):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + tracking


def tracked_w(d, text, font, tracking=4):
    return sum(d.textlength(ch, font=font) + tracking for ch in text) - tracking


def icon(d, cx, cy, r, kind, col):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=WHITE)
    k = r * 0.42
    if kind == "x":
        d.line((cx - k, cy - k, cx + k, cy + k), fill=col, width=11)
        d.line((cx - k, cy + k, cx + k, cy - k), fill=col, width=11)
    elif kind == "check":
        d.line((cx - k * 1.15, cy + k * 0.05, cx - k * 0.25, cy + k * 0.9, cx + k * 1.2, cy - k * 0.8),
               fill=col, width=11, joint="curve")
    else:
        d.text((cx, cy + 2), kind, font=F("Bold", 56), fill=col, anchor="mm")


def prepare(e):
    """Measure once per reel: fonts, wraps, split line, duration."""
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    top_label, bottom_label, teaser, top_icon, q_top, q_bot = SERIES[e["series"]]
    top = typo(e["top"])
    bottom = typo(e["bottom"].replace(";;", "\n"))
    if e["series"] == "F":
        top = "…" + top
    if q_top:
        top = "“" + top + "”"
    if q_bot:
        bottom = "“" + bottom + "”"
    x0, ty = 96, 290
    tf, tlh, tw, tn, ok1 = fit(d, top, "Bold", [104, 92, 80, 70, 62], 1.19, 890, 380)
    split = max(620, ty + 116 + tn * tlh + 64)
    bf, blh, bw, bn, ok2 = fit(d, bottom, "Medium", [84, 76, 68, 62, 56, 50, 46, 42], 1.35, 870,
                               SAFE_BOTTOM - (split + 212))
    nwords = len(bottom.split())
    return {
        "labels": (top_label, bottom_label, teaser, top_icon), "x0": x0, "ty": ty,
        "top": (tf, tw), "bottom": (bf, bw), "split": split,
        "dur": 7.0 if nwords <= 18 else 9.0, "fits": ok1 and ok2,
    }


def frame(t, p):
    top_label, bottom_label, teaser, top_icon = p["labels"]
    x0, ty, split = p["x0"], p["ty"], p["split"]
    img = Image.new("RGB", (W, H), RED)
    d = ImageDraw.Draw(img)
    fl = F("Bold", 38)

    d.text((x0, 190), "@" + HANDLE, font=F("Medium", 34), fill=(255, 214, 214))
    icon(d, x0 + 42, ty + 42, 42, top_icon, RED)
    tracked(d, (x0 + 108, ty + 14), top_label, fl, WHITE)
    tf, tw = p["top"]
    for w, x, y, ww in tw:
        d.text((x0 + x, ty + 116 + y), w, font=tf, fill=WHITE)

    # dark teaser panel
    d.rectangle((0, split, W, H), fill=DARK)
    grey = (150, 150, 158)
    tracked(d, ((W - tracked_w(d, teaser, fl)) / 2, split + 230), teaser, fl, grey)
    for i in range(3):
        on = 0.35 + 0.65 * max(0.0, math.sin(t * 2 * math.pi / 0.9 - i * 0.9))
        cx = W / 2 - 34 + i * 34
        d.ellipse((cx - 8, split + 322 - 8, cx + 8, split + 322 + 8), fill=mix(DARK, grey, on))

    # green panel wipes up
    pr = ease(prog(t, *REVEAL))
    if pr > 0:
        py = H + (split - H) * pr
        d.rectangle((0, py, W, H), fill=GREEN)
        pulse = 1 + 0.06 * max(0.0, math.sin((t - REVEAL[1]) * 2 * math.pi / 2.4)) if t > REVEAL[1] else 1
        icon(d, x0 + 42, py + 90 + 42, 42 * pulse, "check", GREEN)
        tracked(d, (x0 + 108, py + 104), bottom_label, fl, WHITE)
        bf, bw = p["bottom"]
        for w, x, y, ww in bw:
            d.text((x0 + x, py + 212 + y), w, font=bf, fill=WHITE)
    return img


def make_audio(path, dur):
    """Low thud at 0 s and a two-note chime when the green panel lands."""
    expr = ("0.30*sin(2*PI*170*t)*exp(-22*t)"
            "+gte(t,1.3)*0.20*(sin(2*PI*784*(t-1.3))+0.5*sin(2*PI*1176*(t-1.3)))*exp(-6*(t-1.3))")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"aevalsrc='{expr}':s=44100:d={dur}", "-ac", "2", "-c:a", "aac", "-b:a", "128k", path],
                   check=True)


def render(e, outdir):
    p = prepare(e)
    out = os.path.join(outdir, f"{HANDLE}_{e['id']}.mp4")
    silent, audio, tmp = out[:-4] + ".v.mp4", out[:-4] + ".a.m4a", out[:-4] + ".part.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    for i in range(int(p["dur"] * FPS)):
        ff.stdin.write(frame(i / FPS, p).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg failed on " + e["id"])
    make_audio(audio, p["dur"])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", audio, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out)
    os.remove(silent)
    os.remove(audio)
    return out, p


if __name__ == "__main__":
    mode, bank = sys.argv[1], load_bank(sys.argv[2])
    if mode == "still":
        e = bank[sys.argv[3]]
        frame(float(sys.argv[4]), prepare(e)).save(sys.argv[5])
    else:
        ids = sorted(bank) if sys.argv[3] == "all" else sys.argv[3].split(",")
        if mode == "sheet":
            cols = 5
            rows = math.ceil(len(ids) / cols)
            cw, ch = 432, 768
            sheet = Image.new("RGB", (cols * cw, rows * ch), (0, 0, 0))
            for n, i in enumerate(ids):
                p = prepare(bank[i])
                if not p["fits"]:
                    print("DOES NOT FIT:", i)
                sheet.paste(frame(6.0, p).resize((cw, ch), Image.LANCZOS), ((n % cols) * cw, (n // cols) * ch))
            sheet.save(sys.argv[4])
        elif mode == "render":
            os.makedirs(sys.argv[4], exist_ok=True)
            for i in ids:
                out, p = render(bank[i], sys.argv[4])
                print(out, p["dur"], "ok" if p["fits"] else "DOES NOT FIT")
