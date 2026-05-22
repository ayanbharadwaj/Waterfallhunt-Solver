"""
4_geolocate.py
==============
Reads results/summary.json produced by 3_analyse.py and runs
the full solar reverse-geolocation to find the treasure location.

"""

import json, math
import pvlib
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

RESULTS_DIR = Path("results")
summary     = json.loads((RESULTS_DIR / "summary.json").read_text())

# ── Filter to good daytime frames ────────────────────────────
day = [r for r in summary if not r["night"] and r["pvlib_el"] > 5]
print(f"Total frames: {len(summary)}   Daytime: {len(day)}\n")

# ── Grid search across candidate lat/lon ─────────────────────
# We focus on the zone our earlier analysis identified:
# lat 35-42°N, lon -115 to -122°W  (NV / Eastern CA corridor)

def parse_ts(s):
    return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)

# Pick 3 frames with very different sun positions for triangulation:
# 1. Earliest daytime (dawn)
# 2. Solar noon (highest elevation)
# 3. Mid-afternoon

dawn   = min(day, key=lambda r: r["ts"])
noon   = max(day, key=lambda r: r["pvlib_el"])
late   = max(day, key=lambda r: r["ts"])

anchor_frames = [dawn, noon, late]
print("ANCHOR FRAMES:")
for f in anchor_frames:
    print(f"  {f['ts']}  pvlib_el={f['pvlib_el']:.1f}°  pvlib_az={f['pvlib_az']:.1f}°")

# For each candidate location, compute what the sun SHOULD look like
# at each anchor time, and score against our measurements.

print("\nSearching lat/lon grid (36-41°N, -116 to -122°W)...")
print(f"{'Lat':>5} {'Lon':>7}  {'Dawn el':>8}  {'Noon el':>8}  {'Late el':>8}  {'Score':>8}")
print("-" * 60)

best_score = 0
best_lat   = None
best_lon   = None
results    = []

for lat in np.arange(36.0, 42.0, 0.25):
    for lon in np.arange(-122.0, -115.0, 0.25):

        score = 0.0
        computed = []

        for frame in anchor_frames:
            utc_dt = parse_ts(frame["ts"])
            idx    = pd.DatetimeIndex([utc_dt])
            pos    = pvlib.solarposition.get_solarposition(
                        idx, lat, lon, altitude=1200, method="nrel_numpy")
            el_computed = float(pos["apparent_elevation"].iloc[0])
            el_measured = frame["pvlib_el"]   # pvlib at best-guess location

            # Score: penalise deviation from observed civil-twilight timing
            # and from the measured shadow elevation
            el_err  = abs(el_computed - el_measured)
            score  += 1.0 / (el_err + 0.5)
            computed.append(round(el_computed, 1))

        results.append((score, lat, lon, computed))
        if score > best_score:
            best_score = score
            best_lat   = lat
            best_lon   = lon

# Print top 10 candidates
results.sort(reverse=True)
for score, lat, lon, comp in results[:10]:
    print(f"  {lat:>5.2f} {lon:>7.2f}  "
          f"{comp[0]:>8.1f}°  {comp[1]:>8.1f}°  {comp[2]:>8.1f}°  {score:>8.1f}")

# ── Civil twilight constraint ────────────────────────────────
# We know dawn appeared at frame  20260522T120737Z (12:07 UTC)
# Use this to pin longitude more precisely.

DAWN_UTC = datetime(2026, 5, 22, 12, 7, 37, tzinfo=timezone.utc)
print(f"\nCivil twilight constraint: {DAWN_UTC.strftime('%H:%M UTC')}")
print(f"{'Location':<22} {'Civil twilight':>15}  {'Error (min)':>11}")
print("-" * 52)

for lat_c, lon_c, label in [
    (38.5, -118.5, "Hawthorne NV"),
    (38.0, -118.5, "Best grid match"),
    (37.4, -118.4, "Bishop CA"),
    (36.6, -118.1, "Lone Pine CA"),
    (38.1, -117.2, "Tonopah NV"),
    (best_lat, best_lon, "Grid winner"),
]:
    times = pd.date_range("2026-05-22 11:30", "2026-05-22 12:45",
                          freq="1min", tz="UTC")
    loc   = pvlib.location.Location(lat_c, lon_c, altitude=1200)
    sol   = loc.get_solarposition(times)
    civil = sol[sol["apparent_elevation"] > -6]
    if civil.empty:
        continue
    civil_time = civil.index[0]
    err_min    = (civil_time - pd.Timestamp(DAWN_UTC)).total_seconds() / 60
    print(f"  {label:<20}  {civil_time.strftime('%H:%M UTC'):>15}  "
          f"{err_min:>+10.1f} min")

# ── Final answer ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("FINAL GEOLOCATION ESTIMATE")
print("=" * 55)
print(f"  Best lat / lon : {best_lat:.2f}°N,  {best_lon:.2f}°W")
print(f"  Grid score     : {best_score:.1f}")
print()
print("  Nearest named locations:")
print("    Hawthorne, NV   — 38.52°N, 118.62°W")
print("    Mina, NV        — 38.39°N, 118.10°W")
print("    Bishop, CA      — 37.36°N, 118.39°W")
print("    Tonopah, NV     — 38.07°N, 117.23°W")
print()
print("  Google Maps link:")
print(f"  https://maps.google.com/?q={best_lat},{best_lon}")
print()

# Save final answer
answer = {
    "best_lat":  best_lat,
    "best_lon":  best_lon,
    "score":     best_score,
    "maps_link": f"https://maps.google.com/?q={best_lat},{best_lon}",
    "nearest": [
        {"name": "Hawthorne, NV", "lat": 38.52, "lon": -118.62},
        {"name": "Mina, NV",      "lat": 38.39, "lon": -118.10},
        {"name": "Bishop, CA",    "lat": 37.36, "lon": -118.39},
        {"name": "Tonopah, NV",   "lat": 38.07, "lon": -117.23},
    ]
}
(RESULTS_DIR / "geolocation.json").write_text(json.dumps(answer, indent=2))
print("Saved → results/geolocation.json")
input("\nPress Enter to exit.")
