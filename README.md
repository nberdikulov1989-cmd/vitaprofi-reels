# VitaProfi Reels

Daily Instagram Reels for [vitaprofi.uz](https://vitaprofi.uz): one vitamin-education video and one in-stock product video, with Uzbek captions.

## How it works

1. `tools/daily.py [YYYY-MM-DD]` picks the day's content:
   - **Vitamin topic**: next unused topic from `data/topics.json` (cycles once all are used).
   - **Product**: in-stock item with an unexpired batch, preferring the biggest discount and skipping anything posted in the last 30 days.
2. `tools/make_video.py` renders each video (1080×1920, 30 fps, H.264 + silent AAC) with Pillow and ffmpeg.
3. Output:
   - `videos/<date>-vitamin.mp4`, `videos/<date>-product.mp4`
   - `posts/<date>.json`: captions, public video URLs, cover frame offsets, status
   - `state/history.json`: posting history used to avoid repeats
4. After the owner approves, the videos are posted to Instagram (`vitaprofiuz`) via the Windsor.ai connector using the GitHub Pages URL.

## Data

- `data/products.json`: catalog snapshot from vitaprofi.uz (public prices, stock, batches). No purchase prices.
- `images/<n>.jpg`: product photos (VitaProfi's own photos from the site).
- `data/topics.json`: 30 pre-written vitamin/mineral topics. Claims are limited to well-established, non-medical wording; every video ends with "Biologik faol qo'shimcha. Dori vositasi emas."

To refresh the catalog after stock changes, re-export the product list from vitaprofi.uz into `data/products.json` (same schema) and add any new images to `images/`.

## Requirements

Python 3.10+, Pillow, ffmpeg. Fonts (Inter, OFL-1.1) are bundled in `assets/fonts/`.
