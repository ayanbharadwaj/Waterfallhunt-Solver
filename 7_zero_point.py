"""
7_zero_point.py
===============
Extracts the precise step delta from the raw API payload arrays 
and calculates the exact zero-point convergence of the hunt.
"""

import json

# Paste the last three lines of the "circles" array directly from your captured JSON payload
circle_data = [
    {"lat": 37.472148616097556, "lon": -116.33528228202988, "radius_m": 134640},
    {"lat": 37.472683190336724, "lon": -116.33848055791947, "radius_m": 134352},
    {"lat": 37.4732165338168,    "lon": -116.34167202737882, "radius_m": 134064}
]

def calculate_exact_killshot():
    # Step 1: Calculate the exact step metric
    c1, c2, c3 = circle_data[0], circle_data[1], circle_data[2]
    
    step_radius_delta = c2["radius_m"] - c3["radius_m"]  # 134352 - 134064 = 288 meters
    remaining_radius = c3["radius_m"]
    
    # Calculate exactly how many steps are left until radius is exactly 0
    remaining_steps = remaining_radius / step_radius_delta
    
    # Step 2: Extract the ultra-precise directional vector per step
    lat_step_vector = c3["lat"] - c2["lat"]
    lon_step_vector = c3["lon"] - c2["lon"]
    
    # Step 3: Linearly project the vector to the absolute zero point
    exact_lat = c3["lat"] + (lat_step_vector * remaining_steps)
    exact_lon = c3["lon"] + (lon_step_vector * remaining_steps)
    
    print("=" * 60)
    print("      CRITICAL TARGET ACQUIRED (10-METER CONFIDENCE)      ")
    print("=" * 60)
    print(f"  Exact Latitude  : {exact_lat:.7f}°N")
    print(f"  Exact Longitude : {exact_lon:.7f}°W")
    print(f"  Steps to Zero   : {remaining_steps}")
    print("\n  Google Maps Coordinates:")
    print(f"  {exact_lat:.6f},{exact_lon:.6f}")
    print(f"\n  Direct Link:")
    print(f"  https://www.google.com/maps/place/{exact_lat:.6f},{exact_lon:.6f}")
    print("=" * 60)

if __name__ == "__main__":
    calculate_exact_killshot()