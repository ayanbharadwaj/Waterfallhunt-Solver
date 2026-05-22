"""
5_skyline.py
============
Extracts a 1D pixel silhouette of the distant ridgeline from a target camera frame 
using OpenCV (Gaussian blur and Otsu's thresholding). It then casts synthetic 15km 
lines of sight across a 30m SRTM Digital Elevation Model (DEM) and cross-correlates 
the 3D terrain against the image pixels to pinpoint the exact camera location.

NOTE: Final target coordinates (BEST_LAT, BEST_LON) have been intentionally 
redacted and replaced with impossible dummy values to protect the active hunt.

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
    extractor = SkylineExtractor("frames/REDACTED_TIMESTAMP.webp") # Redacted to dummy values
    image_profile = extractor.extract_silhouette()
    
    print("2. Loading DEM for primary search box...")
    try:
        engine = TopographyEngine("dem_target_area.tif") # Redacted to dummy values
    except rasterio.errors.RasterioIOError:
        print("ERROR: Missing 'dem_37_118.tif'. Download the SRTM tile first.")
        return
        
    # Scan a focused 5km by 5km box around the best solar convergence
    lats = np.arange(28.42, 28.44, 0.001) # Redacted to dummy values
    lons = np.arange(-228.62, -228.58, 0.001) # Redacted to dummy values
    
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
    print(f"TARGET ACQUIRED: {best_loc[0]:.4f}°N, {best_loc[1]:.4f}°W")
    print(f"Match Confidence: {best_score:.2f}")
    print(f"https://maps.google.com/?q={best_loc[0]},{best_loc[1]}")
    print("="*55)

if __name__ == "__main__":
    main()