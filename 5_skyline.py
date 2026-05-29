"""
5_skyline.py
============
Extracts a 1D pixel silhouette of the distant ridgeline from a target camera frame 
using OpenCV. It then casts synthetic 15km lines of sight across a 30m SRTM DEM 
and cross-correlates the 3D terrain against the image pixels to pinpoint the 
exact camera location.
"""

import cv2
import numpy as np
import math
import rasterio 
from scipy.signal import correlate
import itertools
from tqdm import tqdm

class SkylineExtractor:
    def __init__(self, image_path):
        self.img = cv2.imread(str(image_path))
        self.h, self.w = self.img.shape[:2]
        
    def extract_silhouette(self):
        # Convert to grayscale and blur images slightly
        gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Otsu's thresholding method will seperate the bright sky from the dark terrain
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Find the highest dark pixel in each column to form the skyline 1D array
        skyline = np.zeros(self.w)
        for x in range(self.w):
            column = thresh[:, x]
            ground_pixels = np.where(column == 0)[0]
            if len(ground_pixels) > 0:
                skyline[x] = self.h - ground_pixels[0] 
                
        # Normalize to 0-1 for correlation
        skyline = skyline - np.min(skyline)
        if np.max(skyline) > 0:
            skyline = skyline / np.max(skyline)
            
        return skyline

class TopographyEngine:
    def __init__(self, dem_path):
        self.dataset = rasterio.open(dem_path)
        self.dem_data = self.dataset.read(1)
        self.transform = self.dataset.transform
        
    def generate_synthetic_skyline(self, lat, lon, heading_deg, fov_deg=60, resolution=300):
        """Casts rays to calculate max elevation angle, simulating what the camera sees."""
        skyline = np.zeros(resolution)
        start_angle = heading_deg - (fov_deg / 2)
        
        for i in range(resolution):
            angle = math.radians(start_angle + (i / resolution) * fov_deg)
            dx = math.sin(angle)
            dy = math.cos(angle)
            
            max_el_angle = -90.0
            
            # Cast a ray outward for 15km stepping every 250m for speed
            for distance in range(100, 15000, 250):
                target_lon = lon + (dx * distance) / 88000
                target_lat = lat + (dy * distance) / 111000
                
                try:
                    row, col = self.dataset.index(target_lon, target_lat)
                    elev = self.dem_data[row, col]
                    
                    # Observer elevation + 2m camera tripod height (if needed exists)
                    obs_row, obs_col = self.dataset.index(lon, lat)
                    obs_elev = self.dem_data[obs_row, obs_col] + 2 
                    
                    delta_h = elev - obs_elev
                    angle_el = math.degrees(math.atan2(delta_h, distance))
                    
                    if angle_el > max_el_angle:
                        max_el_angle = angle_el
                except IndexError:
                    continue # Ray went off the DEM edge
                    
            skyline[i] = max_el_angle
            
        # Normalize the synthetic skyline
        skyline = skyline - np.min(skyline)
        if np.max(skyline) > 0:
            skyline = skyline / np.max(skyline)
            
        return skyline

def main():
    print("1. Extracting skyline from frame...")
    extractor = SkylineExtractor("frames/20260522T155454Z.webp") 
    image_profile = extractor.extract_silhouette()
    
    print("2. Loading DEM for primary search box...")
    try:
        engine = TopographyEngine("N37W117.tif") 
    except rasterio.errors.RasterioIOError:
        print("ERROR: Missing 'N37W117.tif'. Download the SRTM tile first.")
        return
        
    # COARSE GRID: Centered around the leaked JSON target (37.4732, -116.3416)
    lats = np.arange(37.43, 37.52, 0.005) 
    lons = np.arange(-116.40, -116.29, 0.005) 
    
    best_score = -1
    best_loc = (0, 0)
    
    # Flatten the arrays into a single list of coordinate pairs
    coords = list(itertools.product(lats, lons))
    
    print(f"3. Raycasting synthetic skylines across {len(coords)} coordinates...")
    
    # Wrap the loop with tqdm for a nice, clean loading bar
    for lat, lon in tqdm(coords, desc="Processing Grid", unit="coord"):
        synth_profile = engine.generate_synthetic_skyline(lat, lon, heading_deg=160)
        
        # Cross-correlate image skyline with the DEM skyline
        correlation = np.max(correlate(image_profile, synth_profile))
        
        if correlation > best_score:
            best_score = correlation
            best_loc = (lat, lon)
                
    print("\n" + "="*55)
    print("PASS 1 (COARSE) TARGET ACQUIRED")
    print(f"Coordinates: {best_loc[0]:.4f}°N, {best_loc[1]:.4f}°W")
    print(f"Match Confidence: {best_score:.2f}")
    print(f"https://maps.google.com/?q={best_loc[0]},{best_loc[1]}")
    print("="*55)
    print("\nNow update the bounding box in the code to a 1km area around this target,")
    print("change the step size to 0.001, and run Pass 2 for the final coordinate.")

if __name__ == "__main__":
    main()