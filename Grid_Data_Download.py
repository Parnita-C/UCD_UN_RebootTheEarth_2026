import os
import urllib.request
import rioxarray as rxr

# 1. Load your preprocessed Organic Matter map as the master template
template_path = "cv_om_kg_sq_m.tif"

if not os.path.exists(template_path):
    raise FileNotFoundError(
        f"Could not find '{template_path}'. Please ensure your preprocessed "
        "organic matter raster is in the current working directory."
    )

print("Loading template raster (Central Valley Organic Matter)...")
template_raster = rxr.open_rasterio(template_path, masked=True)

# 2. Define the target UC Davis soil properties to download
# Map target filenames to their remote raster names on UC Davis servers
soil_layers = {
    "ph": "ph.tif",  # pH
    "ec": "ec.tif",  # Electrical Conductivity (Salinity)
    "texture_0_25": "texture_025.tif"  # Soil Texture (0 - 25 cm depth)
}

base_url = "https://casoilresource.lawr.ucdavis.edu/800m_grids/rasters/{}"

# 3. Download, align, and clip each layer
for key, remote_file in soil_layers.items():
    raw_filename = f"raw_{key}.tif"
    output_filename = f"cv_{key}.tif"

    # Download raw continental US raster if not present
    if not os.path.exists(raw_filename):
        download_url = base_url.format(remote_file)
        print(f"Downloading {remote_file} from UC Davis Soil Resource Lab...")
        try:
            urllib.request.urlretrieve(download_url, raw_filename)
            print(f"Downloaded: {raw_filename}")
        except Exception as e:
            print(f" Failed to download {remote_file}: {e}")
            continue

    # Process and align to template
    print(f"Aligning {raw_filename} to Central Valley template...")
    try:
        raster = rxr.open_rasterio(raw_filename, masked=True)

        # reproject_match handles CRS transformation, clipping, and pixel alignment simultaneously
        aligned_raster = raster.rio.reproject_match(template_raster)

        # Save output raster
        aligned_raster.rio.to_raster(output_filename)
        print(f"Saved aligned raster: {output_filename}\n")

    except Exception as e:
        print(f" Error processing {raw_filename}: {e}\n")

print("All requested soil property rasters are prepared and aligned!")

