"""
3_analyse.py
============
Reads every .webp in the frames/ folder, runs solar geometry analysis
on each daytime frame, and writes results to results/summary.json.

"""

import cv2, pvlib, pandas as pd, numpy as np
import json, math
from pathlib import Path
from datetime import datetime, timezone

FRAMES_DIR  = Path("frames")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

# Helpers:

def parse_ts(s):
    """Parse a UTC timestamp string like 20260522T155454Z into datetime."""
    return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)

def sun_position(utc_dt, lat, lon, alt=1200):
    """Return (azimuth, elevation) at a given lat/lon/time via pvlib."""
    idx = pd.DatetimeIndex([utc_dt])
    pos = pvlib.solarposition.get_solarposition(idx, lat, lon,
                                                 altitude=alt,
                                                 method="nrel_numpy")
    return float(pos["azimuth"].iloc[0]), float(pos["apparent_elevation"].iloc[0])

def mean_brightness(bgr):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    return float(lab[:, :, 0].mean())

def sun_elevation_from_shadows(bgr):
    """
    Estimate solar elevation from shadow length vs object height.
    Returns degrees, or None if insufficient contrast.
    """
    h, w = bgr.shape[:2]
    lab  = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L    = lab[:, :, 0].astype(np.float32)

    shadow_mask = (L < np.percentile(L, 30)).astype(np.uint8) * 255
    lit_mask    = (L > np.percentile(L, 65)).astype(np.uint8) * 255

    # gradient from the shadow terminator to the sun's direction
    gx = cv2.Sobel(L, cv2.CV_32F, 1, 0, ksize=11)
    gy = cv2.Sobel(L, cv2.CV_32F, 0, 1, ksize=11)
    k  = np.ones((5, 5), np.uint8)
    boundary = cv2.dilate(shadow_mask, k) & cv2.dilate(lit_mask, k)
    boundary[:int(h * 0.35), :] = 0   # skip the sky zone

    if np.sum(boundary > 0) < 500:
        return None, None

    wx = float(np.sum(gx[boundary > 0]))
    wy = float(np.sum(gy[boundary > 0]))
    image_sun_angle = math.degrees(math.atan2(-wy, wx))  

    # ~ rough elevation from the shadow length heuristic (centre crop)
    cy, cx = h // 2, w // 2
    crop   = bgr[cy-200:cy+200, cx-200:cx+200]
    gray   = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, bright = cv2.threshold(gray, 185, 255, cv2.THRESH_BINARY)
    cnts, _   = cv2.findContours(bright, cv2.RETR_EXTERNAL,
                                  cv2.CHAIN_APPROX_SIMPLE)
    el_est = None
    if cnts:
        largest = max(cnts, key=cv2.contourArea)
        _, _, cw, ch2 = cv2.boundingRect(largest)
        if cw > 5 and ch2 > 5:
            el_est = round(math.degrees(math.atan2(ch2, cw)), 2)

    return image_sun_angle, el_est

# Main Big loop

image_files = sorted(FRAMES_DIR.glob("*.webp"))
print(f"Found {len(image_files)} frames in {FRAMES_DIR}/\n")

# Best candidate location from our solar analysis
BEST_LAT, BEST_LON = 28.4, -228.6

all_results = []
daytime_count = 0

for img_path in image_files:
    ts_str = img_path.stem          # e.g. "20260522T155454Z"
    utc_dt = parse_ts(ts_str)

    bgr = cv2.imread(str(img_path))
    if bgr is None:
        # if webp fallback then we try PIL
        try:
            from PIL import Image
            import numpy as np
            pil = Image.open(img_path).convert("RGB")
            bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        except Exception:
            print(f"SKIP  {ts_str}  (cannot read image)")
            continue

    brightness = mean_brightness(bgr)
    is_night   = brightness < 18

    # Compute PVLIB's sun's position at the best estimated location
    az, el = sun_position(utc_dt, BEST_LAT, BEST_LON)

    record = {
        "ts":         ts_str,
        "utc":        utc_dt.isoformat(),
        "brightness": round(brightness, 1),
        "night":      is_night,
        "pvlib_az":   round(az, 2),
        "pvlib_el":   round(el, 2),
        "img_sun_angle": None,
        "el_estimate":   None,
    }

    if not is_night and el > 3:
        daytime_count += 1
        img_angle, el_est = sun_elevation_from_shadows(bgr)
        record["img_sun_angle"] = round(img_angle, 2) if img_angle else None
        record["el_estimate"]   = el_est

        print(f"DAY   {ts_str}  L={brightness:.0f}  "
              f"pvlib_el={el:.1f}°  el_est={el_est}°")
    else:
        print(f"NIGHT {ts_str}  L={brightness:.0f}")

    all_results.append(record)

# Save all the results
out_path = RESULTS_DIR / "summary.json"
out_path.write_text(json.dumps(all_results, indent=2))
print(f"\nSaved {len(all_results)} records → {out_path}")
print(f"Daytime frames analysed: {daytime_count}")

# Find the ~ solar noon (max elevation frame)
day_frames = [r for r in all_results if not r["night"] and r["pvlib_el"] > 3]
if day_frames:
    noon = max(day_frames, key=lambda r: r["pvlib_el"])
    print(f"\nSolar noon frame:  {noon['ts']}")
    print(f"  pvlib elevation:  {noon['pvlib_el']}°  azimuth: {noon['pvlib_az']}°")
    print(f"  Measured el est:  {noon['el_estimate']}°")

    # Lock the Latitude using the solar noon elevation
    # At solar noon: sun_elevation = 90 - |lat - solar_declination|
    # Solar declination on May 22 ≈ +20.5°
    solar_dec = 20.5
    lat_estimate = 90 - noon["pvlib_el"] + solar_dec
    print(f"\nLatitude estimate from noon elevation: {lat_estimate:.1f}°N")

print("\nAnalysis complete.  Results in results/summary.json")
input("Press Enter to exit.")
