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
import numpy as np
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


SR = 44100
BPM = 100
# Three original chord loops (Hz of root, chord intervals in semitones). Chosen per script id.
PROGRESSIONS = [
    [(220.00, (0, 3, 7)), (174.61, (0, 4, 7)), (130.81, (0, 4, 7, 11)), (196.00, (0, 4, 7))],   # Am F Cmaj7 G
    [(146.83, (0, 3, 7, 10)), (196.00, (0, 4, 7)), (130.81, (0, 4, 7)), (220.00, (0, 3, 7))],  # Dm7 G C Am
    [(174.61, (0, 4, 7, 11)), (164.81, (0, 3, 7)), (146.83, (0, 3, 7)), (196.00, (0, 4, 7))],  # Fmaj7 Em Dm G
]


def _env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(attack, 1e-4)) * np.exp(-t / decay)


def _lowpass(x, cutoff):
    a = math.exp(-2 * math.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):          # one-pole filter; short clips so a loop is fine
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def _add(buf, sig, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[:j - i]


def music(dur, variant):
    """Original lo-fi beat: kick, clap, hats, bass, soft chords, plus the reveal chime."""
    n = int(dur * SR)
    rng = np.random.default_rng(variant)
    beat = 60.0 / BPM
    drums, bass, pad = np.zeros(n), np.zeros(n), np.zeros(n)
    duck = np.ones(n)

    kn = int(0.35 * SR); kt = np.arange(kn) / SR
    kick = np.sin(2 * np.pi * (45 * kt + 75 * (1 - np.exp(-kt * 30)) / 30)) * np.exp(-kt * 9)
    cn = int(0.18 * SR)
    clap = _lowpass(rng.standard_normal(cn), 2500) * _env(cn, 0.001, 0.045) * 1.6
    hn = int(0.05 * SR)
    hat = np.diff(rng.standard_normal(hn + 1)) * _env(hn, 0.0005, 0.012) * 0.25

    b = 0
    while b * beat < dur:
        t = b * beat
        if b % 4 in (0, 2) or (b % 8 == 7):
            _add(drums, kick * 0.9, t)
            d0, d1 = int(t * SR), min(n, int((t + 0.22) * SR))
            duck[d0:d1] = np.minimum(duck[d0:d1], np.linspace(0.45, 1.0, d1 - d0))
        if b % 4 in (1, 3):
            _add(drums, clap * 0.55, t)
        _add(drums, hat, t)
        _add(drums, hat * 0.6, t + beat / 2)
        b += 1

    prog = PROGRESSIONS[variant % len(PROGRESSIONS)]
    bar = 4 * beat
    k = 0
    while k * bar < dur:
        root, ivs = prog[k % len(prog)]
        ln = int(bar * SR); t = np.arange(ln) / SR
        chord = sum(np.sin(2 * np.pi * root * 2 ** (iv / 12) * t + 0.3 * np.sin(2 * np.pi * 2.5 * t))
                    for iv in ivs) / len(ivs)
        _add(pad, chord * _env(ln, 0.08, 3.0) * 0.32, k * bar)
        for q in range(4):            # bass on every beat, octave below root
            bn = int(beat * 0.9 * SR); bt = np.arange(bn) / SR
            note = root / 2 * (2 if q == 3 else 1)
            _add(bass, np.sin(2 * np.pi * note * bt) * _env(bn, 0.005, 0.25) * 0.5, k * bar + q * beat)
        k += 1

    pad = _lowpass(pad, 1800)
    t = np.arange(n) / SR
    chime = (t >= REVEAL[0]) * 0.22 * (np.sin(2 * np.pi * 784 * (t - REVEAL[0])) +
                                       0.5 * np.sin(2 * np.pi * 1176 * (t - REVEAL[0]))) * np.exp(-6 * np.clip(t - REVEAL[0], 0, None))
    mix = drums * 0.8 + (bass + pad) * duck + chime
    fade_in, fade_out = int(0.03 * SR), int(0.5 * SR)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)
    return mix / (np.max(np.abs(mix)) + 1e-9) * 0.89


def make_audio(path, dur, variant=0):
    """Write the music bed as AAC. Original, synthesized here: no licensed music."""
    import wave
    pcm = (np.clip(music(dur, variant), -1, 1) * 32767).astype(np.int16)
    wav = path[:-4] + ".wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "160k", path],
                   check=True)
    os.remove(wav)


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
    make_audio(audio, p["dur"], int(re.sub(r"\D", "", e["id"]) or 0))
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
