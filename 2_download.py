"""
2_download.py
=============
Downloads every camera frame from the waterfallhunt.com API.

Output: frames/  folder full of 20260522T155454Z.webp  files
"""

import requests, time
from pathlib import Path

OUTPUT_DIR = Path("frames")
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "Referer":    "https://waterfallhunt.com/",
    "Origin":     "https://waterfallhunt.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
}

# Step 1 is to pull the full frame list
print("Fetching frame list from API...")
try:
    resp = requests.get(
        "https://api.waterfallhunt.com/api/state",
        headers=HEADERS,
        timeout=15
    )
    resp.raise_for_status()
    state  = resp.json()
    frames = state["cam1_frames"]
    print(f"Found {len(frames)} frames.\n")
except Exception as e:
    print(f"ERROR fetching API: {e}")
    input("Press Enter to exit.")
    raise SystemExit

# Step 2 is to download each one
session = requests.Session()
session.headers.update(HEADERS)

ok = skip = fail = 0

for i, frame in enumerate(frames, 1):
    ts  = frame["id"]                   # e.g. "20260522T155454Z"
    url = f"https://api.waterfallhunt.com{frame['preview_url']}"
    out = OUTPUT_DIR / f"{ts}.webp"

    if out.exists():
        skip += 1
        print(f"[{i:>4}/{len(frames)}] SKIP  {ts}")
        continue

    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        out.write_bytes(r.content)
        kb = len(r.content) // 1024
        ok += 1
        print(f"[{i:>4}/{len(frames)}] OK    {ts}  ({kb} KB)")
    except Exception as e:
        fail += 1
        print(f"[{i:>4}/{len(frames)}] FAIL  {ts}  — {e}")

    time.sleep(0.25)

print(f"\nDone.  OK={ok}  Skipped={skip}  Failed={fail}")
print(f"Images saved to:  {OUTPUT_DIR.resolve()}")
input("Press Enter to exit.")
