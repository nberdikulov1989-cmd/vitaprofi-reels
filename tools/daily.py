#!/usr/bin/env python3
"""Build the two daily VitaProfi Reels: one vitamin-education video and one
in-stock product video, plus Uzbek captions.

Usage: python3 tools/daily.py [YYYY-MM-DD]
Outputs:
  videos/<date>-vitamin.mp4, videos/<date>-product.mp4
  posts/<date>.json   (captions, video URLs, chosen topic/product)
  state/history.json  (what was posted when, to avoid repeats)
"""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_BASE = "https://nberdikulov1989-cmd.github.io/vitaprofi-reels"
RAW_BASE = "https://raw.githubusercontent.com/nberdikulov1989-cmd/vitaprofi-reels/main"
PRODUCT_REPEAT_DAYS = 30

MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
          "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"]
NUT_LABEL = {
    "vitd": "D vitamini", "vitc": "C vitamini", "b": "B vitaminlari", "multi": "Multivitamin",
    "magnesium": "Magniy", "zinc": "Rux", "iron": "Temir", "calcium": "Kalsiy",
    "omega3": "Omega-3", "probiotic": "Probiotik", "biotin": "Biotin", "collagen": "Kollagen",
    "folic": "Foliy kislota", "herbal": "O'simlik qo'shimchasi", "weight": "Sport va vazn",
    "beauty": "Go'zallik",
}
FOOTER = "Biologik faol qo'shimcha. Dori vositasi emas."


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return default


def fmt_sum(n):
    return f"{n:,}".replace(",", " ")


def exp_text(exp):  # "2027-02" -> "2027-yil fevral"
    y, m = exp.split("-")
    return f"{y}-yil {MONTHS[int(m) - 1]}"


def pick_topic(topics, history, day_index):
    used = [h["topic"] for h in history]
    # first topic never used yet, in list order; once all used, cycle by day
    for t in topics:
        if t["id"] not in used:
            return t
    return topics[day_index % len(topics)]


def pick_product(products, history, today):
    cutoff = (today - dt.timedelta(days=PRODUCT_REPEAT_DAYS)).isoformat()
    recent = {h["sku"] for h in history if h["date"] >= cutoff}
    last_used = {}
    for h in history:
        last_used[h["sku"]] = h["date"]
    ym = today.strftime("%Y-%m")
    cands = []
    for p in products:
        live = [b for b in p.get("batches", []) if b["qty"] > 0 and b["exp"] > ym]
        if p.get("stock", 0) <= 0 or not live:
            continue
        cands.append((p["sku"] in recent, last_used.get(p["sku"], ""), -p.get("maxDisc", 0), p["id"], p, live))
    if not cands:
        raise SystemExit("No in-stock product available")
    cands.sort(key=lambda c: c[:4])
    _, _, _, _, p, live = cands[0]
    return p, live


def topic_spec(t):
    return {"scenes": [
        {"type": "title", "dur": 3.0, "kicker": t["kicker"], "title": t["title"], "sub": t["sub"]},
        {"type": "bullets", "dur": 5.0, "title": "Bilib qo'ying", "items": t["facts"]},
        {"type": "bullets", "dur": 4.0, "title": "Esda tuting", "items": [
            t["caution"], "Dozani qadoqdagi ko'rsatmaga qarab tanlang"]},
        {"type": "cta", "dur": 3.5, "title": "Savolingiz bormi?",
         "lines": ["Telegram: @vitaprofiuz", "vitaprofi.uz"], "disclaimer": FOOTER},
    ]}


def product_view(p, live):
    best_batch = min(live, key=lambda b: (b["price"], b["exp"]))
    label = next((NUT_LABEL[n] for n in p.get("nut", []) if n in NUT_LABEL), "Vitamin")
    who = "Bolalar uchun" if "kids" in p.get("ages", []) else (
        "Homiladorlar uchun" if p.get("age") == "Homiladorlar" else "Kattalar uchun")
    kids = "kids" in p.get("ages", [])
    disclaimer = ("Biologik faol qo'shimcha, dori vositasi emas. Dozani qadoq va shifokor tavsiyasiga ko'ra bering."
                  if kids or who == "Homiladorlar uchun" else
                  "Biologik faol qo'shimcha, dori vositasi emas. Qadoqdagi ko'rsatmaga amal qiling.")
    return {
        "label": label, "who": who, "disclaimer": disclaimer,
        "price": p["price"], "sale": best_batch["price"], "disc": best_batch["disc"],
        "exp": best_batch["exp"], "qty": p["stock"], "reasons": best_batch.get("reasons", []),
    }


def product_spec(p, v, image_path):
    discounted = v["sale"] < v["price"]
    notes = [f"so'm · omborda {v['qty']} quti", f"Yaroqlilik muddati: {exp_text(v['exp'])}"]
    if discounted and "expiry" in v["reasons"]:
        notes.append("Chegirma muddat yaqinligi uchun berilgan")
    elif discounted:
        notes.append("Ko'p qoldiq uchun chegirma")
    return {"scenes": [
        {"type": "title", "dur": 3.0, "kicker": "Omborda bor", "title": f"{v['who']}: {v['label']}",
         "sub": f"{p['origin']}dan, asl mahsulot"},
        {"type": "product", "dur": 4.0, "image": image_path,
         "badge": f"-{v['disc']}%" if discounted else None,
         "title": p["name"], "sub": f"{p['pack']} · {p['brand']}"},
        {"type": "price", "dur": 4.5, "old": f"{fmt_sum(v['price'])} so'm" if discounted else None,
         "new": fmt_sum(v["sale"]), "notes": notes},
        {"type": "cta", "dur": 3.5, "title": "Buyurtma bering",
         "lines": ["Telegram: @vitaprofiuz", "vitaprofi.uz"], "disclaimer": v["disclaimer"]},
    ]}


def topic_caption(t):
    facts = "\n".join(f"✅ {f}" for f in t["facts"])
    tags = " ".join(f"#{x}" for x in ["vitaprofi", *t["tags"], "vitaminlar", "sogliq", "toshkent", "ozbekiston"])
    return (f"💡 {t['title']}\n\n{facts}\n\n⚠️ {t['caution']}. Dozani qadoqdagi ko'rsatmaga qarab tanlang. "
            f"Homilador, emizikli yoki dori qabul qilayotgan bo'lsangiz, avval shifokor bilan maslahatlashing.\n\n"
            f"Savollar bo'lsa — Telegram: @vitaprofiuz\n🌐 vitaprofi.uz\n\n{FOOTER}\n\n{tags}")


def product_caption(p, v):
    discounted = v["sale"] < v["price"]
    price = (f"💰 Narxi: {fmt_sum(v['price'])} so'm → {fmt_sum(v['sale'])} so'm (−{v['disc']}%)"
             if discounted else f"💰 Narxi: {fmt_sum(v['sale'])} so'm")
    why = ("\nChegirma muddat yaqinligi uchun berilgan — biz muddatni ochiq ko'rsatamiz."
           if discounted and "expiry" in v["reasons"] else "")
    brand_tag = "".join(ch for ch in p["brand"].lower() if ch.isalnum())
    label_tag = "".join(ch for ch in v["label"].lower() if ch.isalnum())
    tags = " ".join(f"#{x}" for x in ["vitaprofi", brand_tag, label_tag, "chegirma" if discounted else "yangi",
                                      "vitaminlar", "toshkent", "ozbekiston"])
    return (f"🛍 Omborda bor: {p['name']}\n{p['pack']} · {p['origin']}\n\n{p['desc']['uz']}\n\n{price}\n"
            f"📦 Omborda: {v['qty']} quti\n📅 Yaroqlilik muddati: {exp_text(v['exp'])}{why}\n\n"
            f"🛒 Buyurtma: Telegram @vitaprofiuz yoki vitaprofi.uz\n🚚 O'zbekiston bo'ylab yetkazib beramiz\n\n"
            f"{v['disclaimer']}\n\n{tags}")


def render(spec, out):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_video.py"), f.name, out], check=True)
    os.unlink(f.name)


def main():
    tz = ZoneInfo("Asia/Tashkent")
    today = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.datetime.now(tz).date()
    d = today.isoformat()
    catalog = load(os.path.join(ROOT, "data", "products.json"), None)
    topics = load(os.path.join(ROOT, "data", "topics.json"), [])
    hist_path = os.path.join(ROOT, "state", "history.json")
    history = [h for h in load(hist_path, []) if h["date"] != d]  # re-runs replace the day

    topic = pick_topic(topics, history, today.toordinal())
    prod, live = pick_product(catalog["products"], history, today)
    view = product_view(prod, live)
    image = os.path.join(ROOT, "images", f"{prod['img'].split('/')[-1].split('.')[0]}.jpg")

    os.makedirs(os.path.join(ROOT, "videos"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "posts"), exist_ok=True)
    vid_v = f"videos/{d}-vitamin.mp4"
    vid_p = f"videos/{d}-product.mp4"
    render(topic_spec(topic), os.path.join(ROOT, vid_v))
    render(product_spec(prod, view, image), os.path.join(ROOT, vid_p))

    post = {
        "date": d, "catalog_fetched": catalog.get("fetched"),
        "vitamin": {"topic": topic["id"], "video": vid_v, "pages_url": f"{PAGES_BASE}/{vid_v}",
                    "raw_url": f"{RAW_BASE}/{vid_v}", "thumb_offset": 2500, "caption": topic_caption(topic)},
        "product": {"sku": prod["sku"], "name": prod["name"], "video": vid_p,
                    "pages_url": f"{PAGES_BASE}/{vid_p}", "raw_url": f"{RAW_BASE}/{vid_p}",
                    "thumb_offset": 5500, "caption": product_caption(prod, view)},
        "status": "awaiting_approval",
    }
    json.dump(post, open(os.path.join(ROOT, "posts", f"{d}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    history.append({"date": d, "topic": topic["id"], "sku": prod["sku"]})
    json.dump(history, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"date": d, "topic": topic["id"], "sku": prod["sku"], "name": prod["name"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
