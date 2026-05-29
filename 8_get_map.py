"""
8_get_map.py
Bypasses government APIs to pull SRTM data directly from AWS.
"""
import urllib.request
import gzip
import shutil
import os

url = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/N37/N37W117.hgt.gz"
gz_path = "N37W117.hgt.gz"
final_path = "N37W117.hgt"

print("Bypassing government servers...")
print("Downloading DEM tile directly from Amazon AWS Open Data...")
urllib.request.urlretrieve(url, gz_path)

print("Extracting archive...")
with gzip.open(gz_path, 'rb') as f_in:
    with open(final_path, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

os.remove(gz_path)
print(f"SUCCESS! {final_path} is securely downloaded and ready.")