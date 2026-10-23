import os
import geopandas as gpd
import rioxarray as rxr
from shapely.geometry import Point

TEXTURE_LOOKUP = {
    1: "Clay", 2: "Silty Clay", 3: "Sandy Clay",
    4: "Clay Loam", 5: "Silty Clay Loam", 6: "Sandy Clay Loam",
    7: "Loam", 8: "Silt Loam", 9: "Silt",
    10: "Sandy Loam", 11: "Loamy Sand", 12: "Sand"
}

CROP_DATABASE = {
    "tomatoes": {
        "family": "Solanaceae", "n_demand": "high", "salt_tol": "moderate",
        "min_ph": 6.0, "max_ph": 7.0, "pref_textures": ["Loam", "Sandy Loam", "Clay Loam"]
    },
    "peppers": {
        "family": "Solanaceae", "n_demand": "high", "salt_tol": "sensitive",
        "min_ph": 6.0, "max_ph": 6.8, "pref_textures": ["Loam", "Sandy Loam"]
    },
    "corn": {
        "family": "Poaceae", "n_demand": "high", "salt_tol": "moderate",
        "min_ph": 5.8, "max_ph": 7.0, "pref_textures": ["Loam", "Clay Loam", "Silt Loam"]
    },
    "wheat": {
        "family": "Poaceae", "n_demand": "moderate", "salt_tol": "tolerant",
        "min_ph": 6.0, "max_ph": 7.5, "pref_textures": ["Loam", "Clay Loam", "Clay"]
    },
    "alfalfa": {
        "family": "Fabaceae", "n_demand": "fixer", "salt_tol": "tolerant",
        "min_ph": 6.5, "max_ph": 7.8, "pref_textures": ["Loam", "Sandy Loam", "Silt Loam", "Silty Clay Loam"]
    },
    "beans": {
        "family": "Fabaceae", "n_demand": "fixer", "salt_tol": "sensitive",
        "min_ph": 6.0, "max_ph": 7.0, "pref_textures": ["Loam", "Sandy Loam"]
    },
    "cotton": {
        "family": "Malvaceae", "n_demand": "moderate", "salt_tol": "tolerant",
        "min_ph": 5.8, "max_ph": 8.0, "pref_textures": ["Loam", "Sandy Loam", "Clay Loam"]
    }
}


class SoilDataExtractor:
    def __init__(self, data_dir="data"):
        """Loads and prepares the 4 cropped Central Valley GeoTIFF rasters from the specified data directory."""
        self.files = {
            "om": os.path.join(data_dir, "cv_om_kg_sq_m.tif"),
            "ph": os.path.join(data_dir, "cv_ph.tif"),
            "ec": os.path.join(data_dir, "cv_ec.tif"),
            "texture": os.path.join(data_dir, "cv_texture_0_25.tif")
        }

        for name, path in self.files.items():
            if not os.path.exists(path):
                raise FileNotFoundError(f"Missing raster file: {os.path.abspath(path)}")

        self.rasters = {
            k: rxr.open_rasterio(v, masked=True) for k, v in self.files.items()
        }

    def get_soil_profile(self, lat: float, lon: float) -> dict:
        target_crs = self.rasters["om"].rio.crs
        point_geom = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(target_crs)[0]

        profile = {}
        for key, raster in self.rasters.items():
            try:
                val = raster.sel(x=point_geom.x, y=point_geom.y, method="nearest").values[0]
                if val is not None and not str(val) == "nan" and val != -999:
                    profile[key] = float(val)
                else:
                    profile[key] = None
            except Exception:
                profile[key] = None

        # Mask check: Organic Matter defines the boundary mask
        in_cv = profile["om"] is not None

        if not in_cv:
            return {
                "in_central_valley": False,
                "organic_matter_kg_m2": "N/A",
                "ph": "N/A",
                "salinity_ec_ds_m": "N/A",
                "texture_code": None,
                "texture_name": "N/A"
            }

        texture_code = int(profile["texture"]) if profile["texture"] is not None else None

        return {
            "in_central_valley": True,
            "organic_matter_kg_m2": round(profile["om"], 2),
            "ph": round(profile["ph"], 2),
            "salinity_ec_ds_m": round(profile["ec"], 2),
            "texture_code": texture_code,
            "texture_name": TEXTURE_LOOKUP.get(texture_code, "Unknown Texture")
        }


def evaluate_next_crops(past_3_crops: list[str], soil_profile: dict) -> list[dict]:
    if not soil_profile.get("in_central_valley", False):
        return [{"error": "Location is outside the Central Valley coverage area."}]

    past_crops_clean = [c.strip().lower() for c in past_3_crops]
    recent_families = [CROP_DATABASE[c]["family"] for c in past_crops_clean if c in CROP_DATABASE]
    heavy_n_count = sum(1 for c in past_crops_clean if CROP_DATABASE.get(c, {}).get("n_demand") == "high")

    soil_ph = soil_profile.get("ph")
    ec_val = soil_profile.get("salinity_ec_ds_m")
    texture_name = soil_profile.get("texture_name")

    scored_candidates = []

    for candidate, traits in CROP_DATABASE.items():
        score = 80
        reasons = []

        # Rule 1: Family Rotation
        if traits["family"] in recent_families:
            score -= 35
            reasons.append(f"Same family ({traits['family']}) grown recently; high disease risk.")

        # Rule 2: Nitrogen Management
        if heavy_n_count >= 2 and traits["n_demand"] == "fixer":
            score += 20
            reasons.append("Heavy nitrogen users grown recently; legume fixer strongly recommended.")
        elif heavy_n_count >= 2 and traits["n_demand"] == "high":
            score -= 25
            reasons.append("Soil nitrogen depleted by consecutive heavy feeders.")

        # Rule 3: Soil pH Compatibility
        if isinstance(soil_ph, (int, float)):
            if not (traits["min_ph"] <= soil_ph <= traits["max_ph"]):
                score -= 30
                reasons.append(f"Soil pH ({soil_ph}) outside optimal range ({traits['min_ph']}-{traits['max_ph']}).")

        # Rule 4: Salinity Tolerance
        if isinstance(ec_val, (int, float)):
            if ec_val > 2.0 and traits["salt_tol"] == "sensitive":
                score -= 30
                reasons.append(f"EC level ({ec_val} dS/m) exceeds sensitivity threshold.")
            elif ec_val > 2.0 and traits["salt_tol"] == "tolerant":
                score += 10
                reasons.append(f"Tolerant to elevated soil salinity ({ec_val} dS/m).")

        # Rule 5: Soil Texture Suitability
        if texture_name in traits["pref_textures"]:
            score += 10
            reasons.append(f"Well-suited for {texture_name} soil texture.")

        # Normalize score between 0 and 100
        final_score = max(0, min(100, score))

        scored_candidates.append({
            "crop": candidate.title(),
            "score": final_score,
            "reasons": reasons
        })

    scored_candidates.sort(key=lambda x: x["score"], reverse=True)
    return scored_candidates