#!/usr/bin/env python3
"""Render 1080x1350 Instagram product cards (JPEG) and captions.

Usage: python3 tools/make_post.py <out_dir> SKU [SKU ...]
Writes <out_dir>/<SKU>.jpg and <out_dir>/posts.json (captions per SKU).
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import (CREAM, GREEN, GREEN_DARK, INK, LEAF, MUTED, ORANGE, ROOT,  # noqa: E402
                        WHITE, font, wrap)
from daily import NUT_LABEL, exp_text, fmt_sum  # noqa: E402

W, H = 1080, 1350


def best_batch(p):
    live = [b for b in p["batches"] if b["qty"] > 0]
    return min(live, key=lambda b: (b["price"], b["exp"]))


def card(p):
    b = best_batch(p)
    discounted = b["price"] < p["price"]
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)
    d.ellipse((-300, -260, 520, 560), fill=LEAF)
    d.ellipse((700, 1000, 1400, 1700), fill=LEAF)
    im = im.filter(ImageFilter.GaussianBlur(60))
    d = ImageDraw.Draw(im)

    logo = Image.open(os.path.join(ROOT, "assets", "logo.png")).convert("RGBA")
    logo = logo.resize((300, int(logo.height * 300 / logo.width)), Image.LANCZOS)
    im.paste(logo, (60, 56), logo)
    tag = "Omborda bor"
    f = font("Bold", 32)
    tw = d.textlength(tag, font=f)
    d.rounded_rectangle((W - 60 - tw - 48, 56, W - 60, 112), 28, fill=GREEN)
    d.text((W - 60 - tw / 2 - 24, 84), tag, font=f, fill=WHITE, anchor="mm")

    # product photo
    size = 620
    photo = Image.open(os.path.join(ROOT, "images", f"{p['img'].split('/')[-1].split('.')[0]}.jpg")).convert("RGB")
    photo = photo.resize((size, size), Image.LANCZOS)
    top = 150
    x0 = (W - size) // 2
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, top + 20, x0 + size, top + size + 20), 44, fill=(20, 60, 20, 55))
    sh = sh.filter(ImageFilter.GaussianBlur(26))
    im.paste(sh, (0, 0), sh)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), 44, fill=255)
    im.paste(photo, (x0, top), mask)
    d = ImageDraw.Draw(im)
    if discounted:
        cx, cy, r = x0 + size - 6, top + 104, 92  # below the "Omborda bor" pill
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ORANGE)
        d.text((cx, cy), f"-{b['disc']}%", font=font("Black", 54), fill=WHITE, anchor="mm")

    # name
    y = top + size + 46
    fn = font("ExtraBold", 50)
    for line in wrap(d, p["name"], fn, W - 140)[:2]:
        d.text((W / 2, y), line, font=fn, fill=INK, anchor="ma")
        y += 62
    label = next((NUT_LABEL[n] for n in p.get("nut", []) if n in NUT_LABEL), "Vitamin")
    d.text((W / 2, y + 4), f"{p['pack']} · {label} · {p['origin']}", font=font("Medium", 34), fill=MUTED, anchor="ma")
    y += 70

    # price row
    if discounted:
        old = f"{fmt_sum(p['price'])} so'm"
        fo = font("SemiBold", 44)
        ow = d.textlength(old, font=fo)
        new = f"{fmt_sum(b['price'])} so'm"
        fnw = font("Black", 84)
        nw = d.textlength(new, font=fnw)
        total = ow + 40 + nw
        sx = (W - total) / 2
        d.text((sx, y + 34), old, font=fo, fill=MUTED)
        d.line((sx - 4, y + 60, sx + ow + 4, y + 60), fill=ORANGE, width=6)
        d.text((sx + ow + 40, y), new, font=fnw, fill=GREEN)
    else:
        d.text((W / 2, y), f"{fmt_sum(b['price'])} so'm", font=font("Black", 84), fill=GREEN, anchor="ma")
    y += 120

    # info chips
    chips = [f"Muddati: {exp_text(b['exp'])}",
             f"{'Chegirmada' if discounted else 'Omborda'}: {b['qty'] if discounted else p['stock']} quti"]
    fc = font("SemiBold", 32)
    widths = [d.textlength(c, font=fc) + 56 for c in chips]
    sx = (W - (sum(widths) + 20)) / 2
    for c, w in zip(chips, widths):
        d.rounded_rectangle((sx, y, sx + w, y + 58), 29, fill=WHITE, outline=(205, 225, 200), width=2)
        d.text((sx + w / 2, y + 29), c, font=fc, fill=GREEN_DARK, anchor="mm")
        sx += w + 20

    # footer
    d.rectangle((0, H - 92, W, H), fill=GREEN)
    d.text((W / 2, H - 46), "Telegram: @vitaprofiuz   ·   vitaprofi.uz", font=font("Bold", 34), fill=WHITE, anchor="mm")
    d.text((W / 2, H - 112), "Biologik faol qo'shimcha. Dori vositasi emas.", font=font("Medium", 26), fill=MUTED, anchor="mm")
    return im, b, discounted


def caption(p, b, discounted):
    price = (f"💰 {fmt_sum(p['price'])} so'm → {fmt_sum(b['price'])} so'm (−{b['disc']}%)"
             if discounted else f"💰 Narxi: {fmt_sum(b['price'])} so'm")
    stock = (f"📦 Chegirma narxida: {b['qty']} quti" if discounted else f"📦 Omborda: {p['stock']} quti")
    why = ("\nChegirma yaroqlilik muddati yaqinligi uchun berilgan — muddatni ochiq ko'rsatamiz."
           if discounted and "expiry" in b.get("reasons", []) else "")
    kids = "kids" in p.get("ages", []) or p.get("age") == "Homiladorlar"
    disclaimer = ("Biologik faol qo'shimcha, dori vositasi emas. Dozani qadoq va shifokor tavsiyasiga ko'ra bering."
                  if kids else "Biologik faol qo'shimcha, dori vositasi emas. Qadoqdagi ko'rsatmaga amal qiling.")
    label = next((NUT_LABEL[n] for n in p.get("nut", []) if n in NUT_LABEL), "Vitamin")
    brand_tag = "".join(ch for ch in p["brand"].lower() if ch.isalnum())
    label_tag = "".join(ch for ch in label.lower() if ch.isalnum())
    tags = " ".join(f"#{t}" for t in ["vitaprofi", brand_tag, label_tag, "chegirma" if discounted else "vitaminlar",
                                      "vitaminlar", "toshkent", "ozbekiston"] if t)
    tags = " ".join(dict.fromkeys(tags.split()))
    return (f"🛍 {p['name']}\n{p['pack']} · {p['brand']} · {p['origin']}\n\n{p['desc']['uz']}\n\n{price}\n{stock}\n"
            f"📅 Yaroqlilik muddati: {exp_text(b['exp'])}{why}\n\n"
            f"🛒 Buyurtma: Telegram @vitaprofiuz yoki vitaprofi.uz\n🚚 O'zbekiston bo'ylab yetkazib beramiz\n\n"
            f"{disclaimer}\n\n{tags}")


def main():
    out = sys.argv[1]
    skus = sys.argv[2:]
    os.makedirs(out, exist_ok=True)
    prods = {p["sku"]: p for p in json.load(open(os.path.join(ROOT, "data", "products.json")))["products"]}
    res = {}
    for s in skus:
        p = prods[s]
        im, b, disc = card(p)
        path = os.path.join(out, f"{s}.jpg")
        im.save(path, "JPEG", quality=90)
        res[s] = {"name": p["name"], "image": os.path.relpath(path, ROOT), "caption": caption(p, b, disc)}
    json.dump(res, open(os.path.join(out, "posts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(res))


if __name__ == "__main__":
    main()
