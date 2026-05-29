"""
6_master_hunter.py
==================
Multi-data triangulation engine using multi-frame averaging and active player filters.
"""

import cv2
import numpy as np
import math
import rasterio 
from scipy.signal import correlate
import itertools
import requests
from tqdm import tqdm

def get_dead_zones():
    try:
        state = requests.get("https://api.waterfallhunt.com/api/public-state", timeout=10).json()
        players = state.get("community_coordinates", [])
        return [(p["lat"], p["lon"]) for p in players]
    except:
        print("Could not fetch live players. Proceeding without dead zones.")
        return []

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def extract_averaged_skyline(image_paths):
    skylines = []
    for path in image_paths:
        img = cv2.imread(path)
        if img is None: continue
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        skyline = np.zeros(w)
        for x in range(w):
            column = thresh[:, x]
            ground = np.where(column == 0)[0]
            if len(ground) > 0:
                skyline[x] = h - ground[0]
        skylines.append(skyline)

    avg_skyline = np.mean(skylines, axis=0)
    avg_skyline = avg_skyline - np.min(avg_skyline)
    if np.max(avg_skyline) > 0:
        avg_skyline = avg_skyline / np.max(avg_skyline)
    return avg_skyline

class TopographyEngine:
    def __init__(self, dem_path):
        self.dataset = rasterio.open(dem_path)
        self.dem_data = self.dataset.read(1)
        
    def generate_synthetic_skyline(self, lat, lon, heading_deg, fov_deg=60, resolution=300):
        skyline = np.zeros(resolution)
        start_angle = heading_deg - (fov_deg / 2)
        for i in range(resolution):
            angle = math.radians(start_angle + (i / resolution) * fov_deg)
            dx, dy = math.sin(angle), math.cos(angle)
            max_el_angle = -90.0
            for distance in range(100, 15000, 250):
                target_lon = lon + (dx * distance) / 88000
                target_lat = lat + (dy * distance) / 111000
                try:
                    row, col = self.dataset.index(target_lon, target_lat)
                    elev = self.dem_data[row, col]
                    obs_row, obs_col = self.dataset.index(lon, lat)
                    obs_elev = self.dem_data[obs_row, obs_col] + 2 
                    delta_h = elev - obs_elev
                    angle_el = math.degrees(math.atan2(delta_h, distance))
                    if angle_el > max_el_angle: max_el_angle = angle_el
                except IndexError:
                    continue
            skyline[i] = max_el_angle
        skyline = skyline - np.min(skyline)
        if np.max(skyline) > 0:
            skyline = skyline / np.max(skyline)
        return skyline

def main():
    dead_zones = get_dead_zones()
    # Update these with real files you have downloaded inside /frames
    frames = [
        "frames/20260522T141406Z.webp", 
        "frames/20260522T184932Z.webp", 
        "frames/20260522T214217Z.webp"
    ]
    master_skyline = extract_averaged_skyline(frames)
    engine = TopographyEngine("N37W117.tif") 

    lats = np.arange(36.80, 37.05, 0.005) 
    lons = np.arange(-116.95, -116.70, 0.005)
    coords = list(itertools.product(lats, lons))
    
    valid_coords = [c for c in coords if not any(haversine_distance(c[0], c[1], dz[0], dz[1]) < 500 for dz in dead_zones)]

    best_score, best_loc = -1, (0, 0)
    for lat, lon in tqdm(valid_coords, desc="Processing Grid", unit="coord"):
        synth_profile = engine.generate_synthetic_skyline(lat, lon, heading_deg=160)
        correlation = np.max(correlate(master_skyline, synth_profile))
        if correlation > best_score:
            best_score = correlation
            best_loc = (lat, lon)
                
    print(f"\nTARGET ACQUIRED: {best_loc[0]:.4f}°N, {best_loc[1]:.4f}°W (Confidence: {best_score:.2f})")

if __name__ == "__main__":
    main()