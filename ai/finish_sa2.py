"""saiditatwork AI-video (25. nov 2026): krok øverst, THOUGHT IT / SAID IT AT WORK-merke, undertekster, @saiditatwork.
Kjøres i Higgsfield-sandkassen (sandbox_exec): ffmpeg, Pillow, faster-whisper og Montserrat finnes der.
Bruk: python3 finish_sa.py inn.mp4 ut.mp4 "Krok" [CUT_SEK]
Uten CUT_SEK finnes overgangen fantasi -> virkelighet automatisk (typisk 4.5–5.2 s). Skriv ut «cut X» – sjekk at den er rimelig."""
import sys, subprocess, os
from PIL import Image, ImageDraw, ImageFont
src, out, hook = sys.argv[1], sys.argv[2], sys.argv[3]
def find_cut(path):
    """Finner overgangen fantasi -> virkelighet: størst fargeforskjell mellom 0,5 s før og etter (3–7 s)."""
    import numpy as np, glob, tempfile
    tmp = tempfile.mkdtemp()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", "fps=6,scale=54:96", f"{tmp}/f_%03d.png"], check=True)
    fr = [np.asarray(Image.open(f).convert("RGB"), float) for f in sorted(glob.glob(f"{tmp}/f_*.png"))]
    best = (0, 5.0)
    for i in range(18, min(len(fr) - 3, 43)):
        dd = np.abs(fr[i + 3].mean(axis=(0, 1)) - fr[i - 3].mean(axis=(0, 1))).sum() + np.abs(fr[i + 1] - fr[i]).mean()
        if dd > best[0]: best = (dd, (i + 0.5) / 6)
    return round(best[1], 2)
cut = float(sys.argv[4]) if len(sys.argv) > 4 else find_cut(src)
print("cut", cut)
W, H = 1080, 1920
FB = "/usr/share/fonts/truetype/higgsfield/Montserrat-ExtraBold.ttf"
def fnt(s): return ImageFont.truetype(FB, s)
def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur); return lines
def layer(): im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); return im, ImageDraw.Draw(im)
base, d = layer(); size = 70
while True:
    f = fnt(size); ls = wrap(d, hook, f, 940)
    if len(ls) <= 2 or size <= 50: break
    size -= 4
y = 200
for ln in ls:
    tw = d.textlength(ln, font=f); d.text(((W-tw)/2, y), ln, font=f, fill="white", stroke_width=9, stroke_fill="black"); y += int(size*1.18)
label_y = y + 24
fs = fnt(38); tag = "@saiditatwork"; tw = d.textlength(tag, font=fs)
x0 = (W-tw)/2-26; d.rounded_rectangle([x0, 1700, x0+tw+52, 1764], radius=32, fill=(15, 15, 20, 175)); d.text((x0+26, 1710), tag, font=fs, fill=(255, 214, 10))
base.save("/tmp/sa_base.png")
def pill(path, text, col):
    im, d = layer(); f = fnt(46); tw = d.textlength(text, font=f); x = (W-tw)/2-34
    d.rounded_rectangle([x, label_y, x+tw+68, label_y+78], radius=39, fill=col, outline="white", width=4)
    d.text((x+34, label_y+12), text, font=f, fill="white"); im.save(path)
pill("/tmp/sa_thought.png", "THOUGHT IT", (214, 40, 52, 255))
pill("/tmp/sa_said.png", "SAID IT AT WORK", (22, 163, 74, 255))
from faster_whisper import WhisperModel
import re, difflib, json
# finish_sa2 (25. nov 2026): ordtidsstempler + SA_LINES='["topp","bunn-setning 1",...]' snapper tekst til manus.
# Topplinjen slutter før kuttet, bunnlinjene starter etter kuttet, ingen overlapp mellom undertekster.
_segs=WhisperModel("tiny.en", compute_type="int8").transcribe(src, word_timestamps=True)[0]
WD=[(w.start,w.end,w.word.strip()) for sg in _segs for w in sg.words if w.word.strip()]
norm=lambda t: re.sub(r"[^a-z0-9' ]","",t.lower().replace("’","'")).split()
known=json.loads(os.environ.get("SA_LINES","[]"))
segs=[]
if known and WD:
    wn=[(" ".join(norm(w[2]))) for w in WD]; p=0
    for k in known:
        kn=norm(k); L=len(kn); best=(0,None)
        for i in range(p,len(WD)):
            for l in range(max(1,L-3),L+4):
                if i+l>len(WD): break
                r=difflib.SequenceMatcher(None," ".join(kn)," ".join(wn[i:i+l])).ratio()
                if r>best[0]: best=(r,(i,i+l))
        if best[1] and best[0]>=0.6:
            i,j=best[1]; segs.append((WD[i][0],WD[j-1][1],k)); p=j
        else: print("NOMATCH",k,round(best[0],2))
else:
    cur=[]
    for w in WD:
        cur.append(w)
        if re.search(r"[.?!]$",w[2]): segs.append((cur[0][0],cur[-1][1]," ".join(x[2] for x in cur))); cur=[]
    if cur: segs.append((cur[0][0],cur[-1][1]," ".join(x[2] for x in cur)))
if known and segs:
    segs=[(a, min(b, cut-0.45), t) if i==0 else (max(a, cut+0.1), b, t) for i,(a,b,t) in enumerate(segs)]
    segs=[(a, max(b, a+0.8), t) for a,b,t in segs]
segs=[(a, min(b, segs[i+1][0]-0.45) if i+1<len(segs) else b, t) for i,(a,b,t) in enumerate(segs)]
caps = []
for i, (a, b, t) in enumerate(segs):
    im, d = layer(); f = fnt(58); ls = wrap(d, t, f, 900); yy = 1420 - (len(ls)-1)*70
    for ln in ls:
        tw = d.textlength(ln, font=f); d.text(((W-tw)/2, yy), ln, font=f, fill=(255, 235, 59), stroke_width=8, stroke_fill="black"); yy += 70
    p = f"/tmp/sa_cap{i}.png"; im.save(p); caps.append((p, a, b + 0.4))
inputs = ["-i", src, "-i", "/tmp/sa_base.png", "-i", "/tmp/sa_thought.png", "-i", "/tmp/sa_said.png"] + sum([["-i", p] for p, _, _ in caps], [])
fc = f"[0:v]scale=1080:1920,setsar=1[v0];[v0][1:v]overlay=0:0[v1];[v1][2:v]overlay=0:0:enable='lt(t,{cut})'[v2];[v2][3:v]overlay=0:0:enable='gte(t,{cut})'[v3]"
last = "v3"
for k, (p, a, b) in enumerate(caps):
    fc += f";[{last}][{4+k}:v]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})'[c{k}]"; last = f"c{k}"
fc += f";[{last}]format=yuv420p[o]"
subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[o]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", "30",
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out + ".part.mp4"], check=True)
os.replace(out + ".part.mp4", out); print("ok", out, segs)
