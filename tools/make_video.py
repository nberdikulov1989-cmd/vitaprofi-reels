#!/usr/bin/env python3
"""VitaProfi Reels generator.

Renders a vertical 1080x1920 MP4 from a JSON scene spec using Pillow + ffmpeg.
Usage: python3 make_video.py spec.json out.mp4

Spec format:
{
  "scenes": [
    {"type": "title",   "dur": 3.0, "kicker": "...", "title": "...", "sub": "..."},
    {"type": "bullets", "dur": 4.0, "title": "...", "items": ["...", "..."]},
    {"type": "product", "dur": 4.0, "image": "assets/p.jpg", "badge": "-45%", "title": "...", "sub": "..."},
    {"type": "price",   "dur": 3.5, "old": "190 000 so'm", "new": "104 000 so'm", "notes": ["..."]},
    {"type": "cta",     "dur": 3.0, "title": "...", "lines": ["...", "..."], "disclaimer": "..."}
  ]
}
"""
import json
import os
import math
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
GREEN = (35, 128, 31)
GREEN_DARK = (18, 74, 22)
LEAF = (226, 242, 220)
CREAM = (248, 251, 245)
INK = (16, 34, 22)
MUTED = (88, 108, 92)
ORANGE = (238, 108, 36)
WHITE = (255, 255, 255)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")
_font_cache = {}


def font(weight, size):
    key = (weight, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(os.path.join(FONT_DIR, f"Inter-{weight}.otf"), size)
    return _font_cache[key]


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


class Renderer:
    def __init__(self, logo_path=os.path.join(ROOT, "assets", "logo.png")):
        self.logo = Image.open(logo_path).convert("RGBA")
        lw = 420
        self.logo = self.logo.resize((lw, int(self.logo.height * lw / self.logo.width)), Image.LANCZOS)
        self.bg = self._make_bg()
        self.img_cache = {}

    def _make_bg(self):
        # Draw blobs directly on an opaque RGB canvas, then blur it, so edges
        # fade into the cream colour instead of into dark transparent pixels.
        bg = Image.new("RGB", (W, H), CREAM)
        d = ImageDraw.Draw(bg)
        d.ellipse((-380, -300, 620, 700), fill=LEAF)
        d.ellipse((560, 1350, 1500, 2300), fill=LEAF)
        d.ellipse((780, 220, 1180, 620), fill=(236, 246, 231))
        return bg.filter(ImageFilter.GaussianBlur(60))

    def base(self):
        im = self.bg.copy()
        im.paste(self.logo, ((W - self.logo.width) // 2, 110), self.logo)
        d = ImageDraw.Draw(im)
        f = font("SemiBold", 34)
        txt = "vitaprofi.uz  ·  Telegram: @vitaprofiuz"
        d.text(((W - d.textlength(txt, font=f)) / 2, H - 120), txt, font=f, fill=MUTED)
        return im

    # Draw text with slide-up + fade entrance.
    def anim_text(self, im, xy, text, fnt, fill, t, delay=0.0, anchor="la"):
        p = ease_out((t - delay) / 0.55)
        if p <= 0:
            return
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        x, y = xy
        d.text((x, y + (1 - p) * 60), text, font=fnt, fill=(*fill, int(255 * p)), anchor=anchor)
        im.paste(layer, (0, 0), layer)

    def scene_title(self, s, t):
        im = self.base()
        d = ImageDraw.Draw(im)
        y = 640
        if s.get("kicker"):
            f = font("Bold", 44)
            tw = d.textlength(s["kicker"], font=f)
            p = ease_out(t / 0.5)
            pill = Image.new("RGBA", im.size, (0, 0, 0, 0))
            pd = ImageDraw.Draw(pill)
            pd.rounded_rectangle(((W - tw) / 2 - 36, y - 18, (W + tw) / 2 + 36, y + 66), 42,
                                 fill=(*GREEN, int(255 * p)))
            pd.text((W / 2, y + 24), s["kicker"], font=f, fill=(*WHITE, int(255 * p)), anchor="mm")
            im.paste(pill, (0, 0), pill)
            y += 150
        f = font("ExtraBold", 92)
        for i, line in enumerate(wrap(d, s["title"], f, W - 140)):
            self.anim_text(im, (W / 2, y), line, f, INK, t, 0.15 + i * 0.12, anchor="ma")
            y += 110
        if s.get("sub"):
            y += 30
            f = font("Medium", 48)
            for i, line in enumerate(wrap(d, s["sub"], f, W - 180)):
                self.anim_text(im, (W / 2, y), line, f, MUTED, t, 0.55 + i * 0.1, anchor="ma")
                y += 64
        return im

    def scene_bullets(self, s, t):
        im = self.base()
        d = ImageDraw.Draw(im)
        y = 420
        f = font("ExtraBold", 72)
        for i, line in enumerate(wrap(d, s["title"], f, W - 160)):
            self.anim_text(im, (90, y), line, f, GREEN_DARK, t, i * 0.1)
            y += 88
        y += 60
        fb = font("SemiBold", 50)
        for i, item in enumerate(s["items"]):
            delay = 0.45 + i * 0.45
            p = ease_out((t - delay) / 0.5)
            lines = wrap(d, item, fb, W - 300)
            card_h = 60 + len(lines) * 66
            if p > 0:
                card = Image.new("RGBA", im.size, (0, 0, 0, 0))
                cd = ImageDraw.Draw(card)
                off = (1 - p) * 80
                cd.rounded_rectangle((70 + off, y, W - 70 + off, y + card_h), 36,
                                     fill=(255, 255, 255, int(235 * p)))
                cd.ellipse((110 + off, y + 38, 160 + off, y + 88), fill=(*GREEN, int(255 * p)))
                cd.text((135 + off, y + 63), str(i + 1), font=font("Bold", 30),
                        fill=(*WHITE, int(255 * p)), anchor="mm")
                ty = y + 30
                for line in lines:
                    cd.text((200 + off, ty), line, font=fb, fill=(*INK, int(255 * p)))
                    ty += 66
                im.paste(card, (0, 0), card)
            y += card_h + 34
        return im

    def _img(self, path):
        if path not in self.img_cache:
            self.img_cache[path] = Image.open(path).convert("RGB")
        return self.img_cache[path]

    def scene_product(self, s, t, dur):
        im = self.base()
        d = ImageDraw.Draw(im)
        src = self._img(s["image"])
        size = 860
        zoom = 1.0 + 0.08 * (t / dur)  # slow Ken Burns
        z = src.resize((int(size * zoom), int(size * zoom)), Image.LANCZOS)
        cx = (z.width - size) // 2
        z = z.crop((cx, cx, cx + size, cx + size))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), 56, fill=255)
        p = ease_out(t / 0.6)
        mask = mask.point(lambda v: int(v * p))
        top = 330 + int((1 - p) * 60)
        shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(((W - size) // 2, top + 24, (W + size) // 2, top + size + 24),
                                                 56, fill=(20, 60, 20, int(60 * p)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(30))
        im.paste(shadow, (0, 0), shadow)
        im.paste(z, ((W - size) // 2, top), mask)
        if s.get("badge"):
            bp = ease_out((t - 0.5) / 0.4)
            if bp > 0:
                r = int(120 * (0.6 + 0.4 * bp))
                badge = Image.new("RGBA", im.size, (0, 0, 0, 0))
                bd = ImageDraw.Draw(badge)
                cx, cy = W - 200, top + 60
                bd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*ORANGE, int(255 * bp)))
                bd.text((cx, cy), s["badge"], font=font("Black", 66), fill=(*WHITE, int(255 * bp)), anchor="mm")
                im.paste(badge, (0, 0), badge)
        y = top + size + 70
        f = font("ExtraBold", 64)
        for i, line in enumerate(wrap(d, s["title"], f, W - 140)):
            self.anim_text(im, (W / 2, y), line, f, INK, t, 0.4 + i * 0.1, anchor="ma")
            y += 78
        if s.get("sub"):
            y += 14
            self.anim_text(im, (W / 2, y), s["sub"], font("Medium", 44), MUTED, t, 0.7, anchor="ma")
        return im

    def scene_price(self, s, t):
        im = self.base()
        d = ImageDraw.Draw(im)
        y = 560
        if s.get("old"):
            f = font("SemiBold", 70)
            p = ease_out(t / 0.5)
            if p > 0:
                layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                tw = ld.textlength(s["old"], font=f)
                ld.text((W / 2, y), s["old"], font=f, fill=(*MUTED, int(255 * p)), anchor="ma")
                sp = ease_out((t - 0.4) / 0.4)
                if sp > 0:
                    x0 = (W - tw) / 2 - 10
                    ld.line((x0, y + 44, x0 + (tw + 20) * sp, y + 44), fill=(*ORANGE, 255), width=9)
                im.paste(layer, (0, 0), layer)
            y += 130
        np_ = ease_out((t - 0.8) / 0.5)
        if np_ > 0:
            scale = 0.8 + 0.2 * np_
            f = font("Black", int(150 * scale))
            layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.text((W / 2, y + 90), s["new"], font=f, fill=(*GREEN, int(255 * np_)), anchor="mm")
            im.paste(layer, (0, 0), layer)
        y += 250
        fn = font("SemiBold", 46)
        for i, note in enumerate(s.get("notes", [])):
            for line in wrap(d, note, fn, W - 200):
                self.anim_text(im, (W / 2, y), line, fn, INK, t, 1.2 + i * 0.25, anchor="ma")
                y += 62
            y += 18
        return im

    def scene_cta(self, s, t):
        im = self.base()
        d = ImageDraw.Draw(im)
        y = 620
        f = font("ExtraBold", 84)
        for i, line in enumerate(wrap(d, s["title"], f, W - 140)):
            self.anim_text(im, (W / 2, y), line, f, GREEN_DARK, t, i * 0.1, anchor="ma")
            y += 100
        y += 60
        p = ease_out((t - 0.4) / 0.5)
        if p > 0:
            layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            n = len(s["lines"])
            ld.rounded_rectangle((110, y, W - 110, y + 70 + n * 76), 40, fill=(*GREEN, int(255 * p)))
            ty = y + 40
            for line in s["lines"]:
                ld.text((W / 2, ty), line, font=font("Bold", 52), fill=(*WHITE, int(255 * p)), anchor="ma")
                ty += 76
            im.paste(layer, (0, 0), layer)
            y += 70 + n * 76
        if s.get("disclaimer"):
            y += 80
            fd = font("Medium", 36)
            for line in wrap(d, s["disclaimer"], fd, W - 220):
                self.anim_text(im, (W / 2, y), line, fd, MUTED, t, 0.9, anchor="ma")
                y += 50
        return im

    def frame(self, s, t):
        kind = s["type"]
        if kind == "title":
            return self.scene_title(s, t)
        if kind == "bullets":
            return self.scene_bullets(s, t)
        if kind == "product":
            return self.scene_product(s, t, s["dur"])
        if kind == "price":
            return self.scene_price(s, t)
        if kind == "cta":
            return self.scene_cta(s, t)
        raise ValueError(f"unknown scene type: {kind}")


def render(spec_path, out_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    r = Renderer()
    total = sum(s["dur"] for s in spec["scenes"])
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=44100:cl=stereo",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "128k", "-shortest",
           "-movflags", "+faststart", out_path]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    fade = int(0.25 * FPS)
    for s in spec["scenes"]:
        n = int(round(s["dur"] * FPS))
        for i in range(n):
            im = r.frame(s, i / FPS)
            # short fade-out at scene end for smoother cuts
            if i >= n - fade:
                a = (n - i) / fade
                im = Image.blend(r.bg, im, max(0.0, min(1.0, a)))
            ff.stdin.write(im.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg failed")


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2])
