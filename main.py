from fastapi import FastAPI
import rasterio
import requests

app = FastAPI(title="Agronomy Chatbot Backend")

# File paths to your California clipped TIFs
BASELINE_CARBON_TIF = "GSOCseq_T0_Map030_CA.tif"
SSM2_CARBON_TIF = "GSOCseq_finalSOC_SSM2_Map030_CA.tif"


def extract_raster_value(tif_path, lat, lon):
    """Extracts a pixel value from a GeoTIFF given lat/lon."""
    try:
        with rasterio.open(tif_path) as src:
            # Convert lat/lon to raster row/column indices
            # Note: rasterio expects (longitude, latitude)
            row, col = src.index(lon, lat)
            value = src.read(1)[row, col]

            # The FAO dataset uses -999 for "no data" outside agricultural land
            if value == -999:
                return None
            return float(value)
    except Exception as e:
        return None


def fetch_soilweb_data(lat, lon):
    """Pings the UC Davis SoilWeb API for live soil classification."""
    # This is a simplified endpoint structure; check SoilWeb documentation for exact parameters
    url = f"https://casoilresource.lawr.ucdavis.edu/soil_web/api/ssurgo.php?lat={lat}&lon={lon}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return {}


@app.get("/analyze_soil")
def analyze_soil(lat: float, lon: float, crop: str = "Almonds"):
    # 1. Get Carbon Data from your local files
    baseline_c = extract_raster_value(BASELINE_CARBON_TIF, lat, lon)
    future_c_ssm2 = extract_raster_value(SSM2_CARBON_TIF, lat, lon)

    # 2. Get Soil Chemistry from UC Davis API
    soil_chemistry = fetch_soilweb_data(lat, lon)

    # 3. FUTURE ML STEP: Pass these values into your scikit-learn classifier
    # crop_suitability_score = my_ml_model.predict([baseline_c, soil_ph, ...])

    # 4. Compile the raw context to feed to your open-source LLM
    context = {
        "location": {"lat": lat, "lon": lon},
        "target_crop": crop,
        "current_carbon_tonnes_ha": baseline_c,
        "potential_carbon_tonnes_ha": future_c_ssm2,
        "carbon_increase_potential": future_c_ssm2 - baseline_c if (future_c_ssm2 and baseline_c) else None,
        "soil_profile": soil_chemistry
    }

    return {"status": "success", "data_for_llm": context}

# To run this server in your PyCharm terminal:
# uvicorn main:app --reload