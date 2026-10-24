import os, re, zipfile, urllib.request
from pathlib import Path
from urllib.parse import urljoin
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import features
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import transform_bounds
import rioxarray as rxr

# ---------- Paths (relative to this .py file, not the working directory) ----------
try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:  # running in a notebook / REPL
    BASE_DIR = Path.cwd()
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DATA_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)

TEMPLATE = DATA_DIR / "cv_om_kg_sq_m.tif"

# ---------- Config ----------
SOIL_PAGE = "https://casoilresource.lawr.ucdavis.edu/soil-properties/download.php"

# key -> (row label on the UC Davis download page, categorical?)
NEW_SOIL_LAYERS = {
    "cec":           ("Cation Exchange Cap. (0 - 25 cm)", False),
    "water_storage": ("Avail. Water Holding Cap. (0 - 25 cm)", False),
}

GSOCSEQ_BASE = "http://54.229.242.119/GSOCseqv1.1/{}"
GSOCSEQ_LAYERS = {
    "soc_t0":   "GSOCseq_T0_Map030.tif",
    "soc_bau":  "GSOCseq_finalSOC_BAU_Map030.tif",
    "rsr_ssm1": "GSOCseq_RSR_SSM1_Map030.tif",
    "rsr_ssm2": "GSOCseq_RSR_SSM2_Map030.tif",
    "rsr_ssm3": "GSOCseq_RSR_SSM3_Map030.tif",
}

DWR = "https://data.cnra.ca.gov/dataset/6c3d65e3-35bb-49e1-a51e-49d5a2cf09a9/resource/{}/download/{}"
CROP_ZIPS = {
    2021: DWR.format("eebd40ab-35a3-4e62-a625-0275b2849531", "i15_crop_mapping_2021_shp.zip"),
    2022: DWR.format("b92e0daf-6e2e-4b5c-a112-09474138d1cd", "i15_crop_mapping_2022_shp.zip"),
    2023: DWR.format("25d0f174-4bec-4987-a402-602cd1372786", "i15_crop_mapping_final_2023.zip"),
}
CROP_COLUMN_CANDIDATES = ["MAIN_CROP", "CROPTYPE2", "CROPTYP2", "CLASS1"]  # first one found is used
SUPERSAMPLE = 10  # fine grid factor used to pick the dominant crop per 800 m cell

# ---------- Helpers ----------
if not TEMPLATE.exists():
    raise FileNotFoundError(f"Missing template: {TEMPLATE}")
template = rxr.open_rasterio(TEMPLATE, masked=True)

def download(url, dest: Path):
    if dest.exists():
        return True
    print(f"Downloading {url}")
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        if dest.exists():
            dest.unlink()
        return False

def align(raw_path: Path, out_path: Path, categorical=False, clip_lonlat=False):
    r = rxr.open_rasterio(raw_path, masked=True)
    if clip_lonlat:  # global rasters: crop to the Valley first to save memory
        w, s, e, n = template.rio.transform_bounds("EPSG:4326")
        r = r.rio.clip_box(minx=w - 0.2, miny=s - 0.2, maxx=e + 0.2, maxy=n + 0.2)
    method = Resampling.nearest if categorical else Resampling.bilinear
    r.rio.reproject_match(template, resampling=method).rio.to_raster(out_path)
    print(f"Saved {out_path}")

# ---------- 1. CEC + water storage (UC Davis, links scraped at runtime) ----------
def scrape_soil_links():
    html = urllib.request.urlopen(SOIL_PAGE).read().decode("utf-8", "ignore")
    links = {}
    for row in re.findall(r"<tr.*?</tr>", html, flags=re.S | re.I):
        text = " ".join(re.sub(r"<[^>]+>", " ", row).split())
        hrefs = [h for h in re.findall(r'href=["\']([^"\']+)', row) if h != "#"]
        if hrefs:
            tif = [h for h in hrefs if "tif" in h.lower()]
            links[text] = urljoin(SOIL_PAGE, (tif or hrefs)[0])
    return links

soil_links = scrape_soil_links()
for key, (label, categorical) in NEW_SOIL_LAYERS.items():
    url = next((u for t, u in soil_links.items() if t.startswith(label)), None)
    if not url:
        print(f"[{key}] no link found for '{label}'; inspect soil_links and set the URL manually")
        continue
    raw = RAW_DIR / f"raw_{key}.tif"
    if download(url, raw):
        align(raw, DATA_DIR / f"cv_{key}.tif", categorical)

# ---------- 2. GSOCseq carbon layers (FAO) ----------
for key, fname in GSOCSEQ_LAYERS.items():
    raw = RAW_DIR / f"raw_{key}.tif"
    if download(GSOCSEQ_BASE.format(fname), raw):
        align(raw, DATA_DIR / f"cv_{key}.tif", categorical=False, clip_lonlat=True)

# ---------- 3. DWR crop history -> dominant crop per template cell ----------
tpl = template.squeeze()
H, W = tpl.sizes["y"], tpl.sizes["x"]
tpl_transform, tpl_crs = tpl.rio.transform(), tpl.rio.crs
crop_codes = {}  # crop name -> integer code, shared across years

def build_crop_layer(year, url):
    zpath = RAW_DIR / f"raw_crop_{year}.zip"
    if not download(url, zpath):
        return
    with zipfile.ZipFile(zpath) as z:
        shp = next(n for n in z.namelist() if n.lower().endswith(".shp"))
    src = f"zip://{zpath}!{shp}"
    file_crs = gpd.read_file(src, rows=1).crs
    bbox = transform_bounds(tpl_crs, file_crs, *tpl.rio.bounds())
    gdf = gpd.read_file(src, bbox=bbox)
    col = next((c for c in CROP_COLUMN_CANDIDATES if c in gdf.columns), None)
    if col is None:
        print(f"[{year}] none of {CROP_COLUMN_CANDIDATES} in columns: {list(gdf.columns)}")
        return
    print(f"[{year}]")