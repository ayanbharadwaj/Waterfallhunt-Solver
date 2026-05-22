# WaterfallHunt Geolocation Pipeline

A Python-based architecture designed to programmatically geolocate a live camera feed using astronomical solar positioning and 3D topographic raycasting.

This pipeline was built to bypass a 3,000km starting radius and reverse-engineer the exact coordinates of the WaterfallHunt challenge purely through mathematical deduction and computer vision.

## 🏗️ Architecture & Methodology

The pipeline operates in three distinct phases, narrowing the search area from a global scale down to a specific line of sight.

### 1. Data Acquisition (`requests`)

The target website streams live frames with embedded UTC timestamps. The `2_download.py` script bypasses the front-end interface, queries the live state API, and bulk-downloads the frame sequence, using the exact UTC timestamps as filenames (e.g., `20260522T155454Z.webp`).

### 2. Solar Chronolocation (`pvlib` & OpenCV)

Before looking at topography, the pipeline establishes a regional bounding box using celestial mechanics:

- **Latitude Lock:** `3_analyse.py` evaluates the luminance and shadow angles across daytime frames to isolate true solar noon. By cross-referencing the sun's azimuth (180.13°) and elevation with the solar declination for that specific day, the latitude is mathematically locked.
- **Longitude Lock:** The script tracks the exact minute of civil twilight (luminance drop-off) and compares it against expected UTC twilight times across the latitude line to lock the longitude.
- **Result:** This isolates a ~40km search box.

### 3. Topographic Cross-Correlation (`rasterio`, `scipy`, OpenCV)

To reduce the 40km box to a specific hillside, `5_skyline.py` shifts from global solar math to local 3D geometry.

- **Skyline Extraction:** Uses Gaussian blur and Otsu's thresholding to strip a 1D pixel silhouette of the distant ridgeline from the target camera frame.
- **DEM Raycasting:** Loads a 30m SRTM Digital Elevation Model (DEM) of the search box. The script iterates through a coordinate grid, casting synthetic 15km lines of sight to calculate the maximum elevation angle (horizon) for every possible location.
- **Peak Matching:** Uses `scipy.signal.correlate` to cross-correlate the synthetic 3D terrain skylines against the real 2D image pixels, isolating the single geographic coordinate with the highest mathematical match.

## ⚙️ Performance Optimization

Calculating 15km lines of sight across a dense geographic grid requires significant computation. Initially, the raycasting engine attempted 126 million elevation checks per block, which completely bottlenecked my local hardware (an Intel i7-4790 with 8GB DDR3 RAM), pushing runtime to >15 minutes per grid.

To optimize for older hardware, the raycasting step size was increased to 250m, coordinate arrays were flattened using `itertools`, and the execution was wrapped in a `tqdm` progress bar, reducing processing time to under a minute without sacrificing the resolution needed to find the target.

## 🔒 A Note on Redactions

To preserve the suspense, anonymity, and integrity of the active WaterfallHunt challenge, I have intentionally redacted the final outputs, specific target frames, and precise DEM filenames from this public repository.

Any hardcoded geographic coordinates in the scripts have been replaced with impossible dummy variables to prevent spoiling the location. For example, the final target convergence variables have been altered like this:

`BEST_LAT, BEST_LON = 28.4, -228.6`

The pipeline, logic, and architecture remain 100% functional. To execute the math, users must scrape their own anchor frames and download the corresponding SRTM topographical tiles for their suspected region.

## Dependencies

- `opencv-python`
- `pvlib`
- `pandas` & `numpy`
- `scipy`
- `rasterio`
- `tqdm`

Run `1_install.bat` to configure the environment.
