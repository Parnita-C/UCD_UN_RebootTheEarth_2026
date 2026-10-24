from __future__ import annotations

import csv
import difflib
import json
from pathlib import Path

import numpy as np
import rioxarray as rxr
from pyproj import Transformer

# ---------- Paths (relative to this file, not the working directory) ----------
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"

REQUIRED_LAYERS = {
    "om": "cv_om_kg_sq_m.tif",
    "ph": "cv_ph.tif",
    "ec": "cv_ec.tif",
    "texture": "cv_texture_0_25.tif",
}
OPTIONAL_LAYERS = {
    "cec": "cv_cec.tif",
    "awc": "cv_water_storage.tif",
    "soc_t0": "cv_soc_t0.tif",
    "soc_bau": "cv_soc_bau.tif",
    "rsr_ssm1": "cv_rsr_ssm1.tif",
    "rsr_ssm2": "cv_rsr_ssm2.tif",
    "rsr_ssm3": "cv_rsr_ssm3.tif",
}
CROP_YEARS = ()
CLASSED_LAYERS = ("om", "cec", "awc", "soc_t0", "soc_bau_change", "rsr_ssm2")  # get low/medium/high labels
GSOC_LAYERS = ("soc_t0", "soc_bau", "soc_bau_change", "rsr_ssm1", "rsr_ssm2", "rsr_ssm3")
GSOC_SEARCH_CELLS = 3  # about 2.4 km at 800 m; GSOCseq is coarse (~1 km) so this is within its precision

# VERIFY against the lookup table on the UC Davis Soil Properties page (Soil Texture 0-25 cm).
TEXTURE_LOOKUP = {
    1: "Sand", 2: "Loamy Sand", 3: "Sandy Loam", 4: "Loam",
    5: "Silt Loam", 6: "Silt", 7: "Sandy Clay Loam", 8: "Clay Loam",
    9: "Silty Clay Loam", 10: "Sandy Clay", 11: "Silty Clay", 12: "Clay",
}
COARSE_TEXTURES = {"Sand", "Loamy Sand", "Sandy Loam"}

# ---------- Crop knowledge (placeholder agronomy: review and edit with an expert) ----------
# n_demand: fixer | low | moderate | high      water_demand: low | moderate | high
# soc_effect: +1 returns lots of residue/carbon, 0 neutral, -1 depletes
CROP_DATABASE = {
    "tomatoes": {"family": "Solanaceae", "n_demand": "high", "salt_tol": "moderate",
                 "min_ph": 6.0, "max_ph": 7.0, "pref_textures": ["Loam", "Sandy Loam", "Clay Loam"],
                 "water_demand": "high", "soc_effect": 0, "role": "cash"},
    "peppers": {"family": "Solanaceae", "n_demand": "high", "salt_tol": "sensitive",
                "min_ph": 6.0, "max_ph": 6.8, "pref_textures": ["Loam", "Sandy Loam"],
                "water_demand": "moderate", "soc_effect": 0, "role": "cash"},
    "corn": {"family": "Poaceae", "n_demand": "high", "salt_tol": "moderate",
             "min_ph": 5.8, "max_ph": 7.0, "pref_textures": ["Loam", "Clay Loam", "Silt Loam"],
             "water_demand": "high", "soc_effect": 1, "role": "cash"},
    "wheat": {"family": "Poaceae", "n_demand": "moderate", "salt_tol": "tolerant",
              "min_ph": 6.0, "max_ph": 7.5, "pref_textures": ["Loam", "Clay Loam", "Clay"],
              "water_demand": "low", "soc_effect": 1, "role": "cash"},
    "alfalfa": {"family": "Fabaceae", "n_demand": "fixer", "salt_tol": "tolerant",
                "min_ph": 6.5, "max_ph": 7.8,
                "pref_textures": ["Loam", "Sandy Loam", "Silt Loam", "Silty Clay Loam"],
                "water_demand": "high", "soc_effect": 1, "role": "cash"},
    "beans": {"family": "Fabaceae", "n_demand": "fixer", "salt_tol": "sensitive",
              "min_ph": 6.0, "max_ph": 7.0, "pref_textures": ["Loam", "Sandy Loam"],
              "water_demand": "moderate", "soc_effect": 0, "role": "cash"},
    "cotton": {"family": "Malvaceae", "n_demand": "moderate", "salt_tol": "tolerant",
               "min_ph": 5.8, "max_ph": 8.0, "pref_textures": ["Loam", "Sandy Loam", "Clay Loam"],
               "water_demand": "high", "soc_effect": 0, "role": "cash"},
    "legume cover crop": {"family": "Fabaceae", "n_demand": "fixer", "salt_tol": "moderate",
                          "min_ph": 6.0, "max_ph": 7.5, "pref_textures": [],
                          "water_demand": "low", "soc_effect": 1, "role": "cover"},
}

ALIASES = {
    "tomato": "tomatoes", "processing tomatoes": "tomatoes", "pepper": "peppers",
    "bell peppers": "peppers", "maize": "corn", "field corn": "corn", "bean": "beans",
    "dry beans": "beans", "hay": "alfalfa", "cover crop": "legume cover crop",
    "vetch": "legume cover crop", "clover": "legume cover crop",
}

N_EFFECT = {"fixer": 1, "low": 0, "moderate": -1, "high": -2}      # relative N balance
N_NEED_BASE = {"fixer": 0, "low": 1, "moderate": 2, "high": 3}     # fertilizer need index
FERT_LABEL = ["none", "low", "moderate", "high"]
WATER_LEVEL = {"low": 1, "moderate": 2, "high": 3}
RECENCY_WEIGHTS = [0.5, 0.75, 1.0]                                  # oldest -> newest
SALT_THRESHOLD_DS_M = {"sensitive": 1.5, "moderate": 3.0, "tolerant": 6.0}


# ---------- Data access ----------
class SoilDataExtractor:
    def __init__(self, data_dir=None):
        """Loads the Central Valley rasters. Required layers must exist; optional ones are skipped if missing."""
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.rasters = {}
        self.missing_optional = []

        for key, fname in REQUIRED_LAYERS.items():
            path = self.data_dir / fname
            if not path.exists():
                raise FileNotFoundError(f"Missing raster file: {path}")
            self.rasters[key] = rxr.open_rasterio(path, masked=True)

        optional = dict(OPTIONAL_LAYERS)
        optional.update({f"crop_{y}": f"cv_crop_{y}.tif" for y in CROP_YEARS})
        for key, fname in optional.items():
            path = self.data_dir / fname
            if path.exists():
                self.rasters[key] = rxr.open_rasterio(path, masked=True)
            else:
                self.missing_optional.append(fname)

        ref = self.rasters["om"]
        self._to_raster_crs = Transformer.from_crs("EPSG:4326", ref.rio.crs, always_xy=True)
        self._tolerance = abs(ref.rio.resolution()[0])  # reject points outside the raster extent

        # Derived layer: projected SOC change under business-as-usual (negative = carbon declining)
        if "soc_t0" in self.rasters and "soc_bau" in self.rasters:
            t0, bau = self.rasters["soc_t0"], self.rasters["soc_bau"]
            if t0.shape == bau.shape:
                self.rasters["soc_bau_change"] = bau.copy(data=bau.values - t0.values)

        # Relative classes (terciles over the Valley) so we don't hard-code units for new layers
        self.breaks = {}
        for key in CLASSED_LAYERS:
            if key in self.rasters:
                arr = self.rasters[key].values
                if np.isfinite(arr).any():
                    self.breaks[key] = tuple(np.nanpercentile(arr, [33.3, 66.7]))

        self.crop_lookup = {}
        lookup_path = self.data_dir / "cv_crop_lookup.csv"
        if lookup_path.exists():
            with open(lookup_path, newline="", encoding="utf-8") as f:
                self.crop_lookup = {int(r["code"]): r["crop"] for r in csv.DictReader(f)}

    def _sample(self, key, x, y):
        if key not in self.rasters:
            return None
        try:
            val = float(self.rasters[key].sel(x=x, y=y, method="nearest",
                                              tolerance=self._tolerance).values[0])
        except (KeyError, IndexError):
            return None
        return None if np.isnan(val) or val == -999 else val

    def _sample_near(self, key, x, y, radius=GSOC_SEARCH_CELLS):
        """Nearest valid cell within `radius` cells, for coarse, agriculture-only layers."""
        val = self._sample(key, x, y)
        if val is not None or key not in self.rasters:
            return val
        da = self.rasters[key]
        xs, ys = da.x.values, da.y.values
        i, j = int(np.abs(xs - x).argmin()), int(np.abs(ys - y).argmin())
        j0, j1 = max(0, j - radius), min(len(ys), j + radius + 1)
        i0, i1 = max(0, i - radius), min(len(xs), i + radius + 1)
        win = da.values[0, j0:j1, i0:i1]
        jj, ii = np.nonzero(np.isfinite(win))
        if len(jj) == 0:
            return None
        dist = (xs[i0:i1][ii] - x) ** 2 + (ys[j0:j1][jj] - y) ** 2
        k = int(dist.argmin())
        return float(win[jj[k], ii[k]])

    def _classify(self, key, value):
        if value is None or key not in self.breaks:
            return None
        lo, hi = self.breaks[key]
        return "low" if value <= lo else "high" if value >= hi else "medium"

    @staticmethod
    def _r(value, nd=2):
        return None if value is None else round(value, nd)

    def get_soil_profile(self, lat: float, lon: float) -> dict:
        x, y = self._to_raster_crs.transform(lon, lat)
        vals = {k: (self._sample_near(k, x, y) if k in GSOC_LAYERS else self._sample(k, x, y))
                for k in self.rasters}

        if vals["om"] is None:  # organic matter raster defines the Central Valley mask
            return {"in_central_valley": False, "organic_matter_kg_m2": "N/A", "ph": "N/A",
                    "salinity_ec_ds_m": "N/A", "texture_code": None, "texture_name": "N/A"}

        tex_code = int(vals["texture"]) if vals["texture"] is not None else None
        history = {}
        for yr in CROP_YEARS:
            code = vals.get(f"crop_{yr}")
            if code is not None and int(code) in self.crop_lookup:
                history[yr] = self.crop_lookup[int(code)]

        return {
            "in_central_valley": True,
            "organic_matter_kg_m2": self._r(vals["om"]),
            "ph": self._r(vals["ph"]),
            "salinity_ec_ds_m": self._r(vals["ec"]),
            "texture_code": tex_code,
            "texture_name": TEXTURE_LOOKUP.get(tex_code, "Unknown Texture") if tex_code else "Unknown Texture",
            "cec_cmol_kg": self._r(vals.get("cec")),
            "awc_cm": self._r(vals.get("awc")),
            "soc_t0": self._r(vals.get("soc_t0")),
            "soc_bau": self._r(vals.get("soc_bau")),
            "soc_bau_change": self._r(vals.get("soc_bau_change")),
            "rsr_ssm1": self._r(vals.get("rsr_ssm1"), 4),
            "rsr_ssm2": self._r(vals.get("rsr_ssm2"), 4),
            "rsr_ssm3": self._r(vals.get("rsr_ssm3"), 4),
            "classes": {k: self._classify(k, vals.get(k)) for k in CLASSED_LAYERS},
            "mapped_crop_history": history,  # DWR-mapped crop at this location, by year
        }
    def close(self):
        for r in self.rasters.values():
            r.close()
        self.rasters.clear()

# ---------- History analysis ----------
def normalize_crop(name: str):
    n = name.strip().lower()
    n = ALIASES.get(n, n)
    if n in CROP_DATABASE:
        return n
    match = difflib.get_close_matches(n, list(CROP_DATABASE), n=1, cutoff=0.8)
    return match[0] if match else None


def analyze_history(past_3_crops: list[str]) -> dict:
    """past_3_crops is ordered oldest -> newest."""
    crops, unknown = [], []
    for c in past_3_crops:
        key = normalize_crop(c)
        (crops if key else unknown).append(key or c)

    weights = RECENCY_WEIGHTS[-len(crops):] if crops else []
    n_pool = sum(w * N_EFFECT[CROP_DATABASE[c]["n_demand"]] for c, w in zip(crops, weights))
    water_pool = sum(w * WATER_LEVEL[CROP_DATABASE[c]["water_demand"]] for c, w in zip(crops, weights))
    family_weight, family_count = {}, {}
    for c, w in zip(crops, weights):
        fam = CROP_DATABASE[c]["family"]
        family_weight[fam] = max(family_weight.get(fam, 0), w)
        family_count[fam] = family_count.get(fam, 0) + 1

    last_is_fixer = bool(crops) and CROP_DATABASE[crops[-1]]["n_demand"] == "fixer"
    if n_pool <= -2.5:
        n_status = "depleted"
    elif n_pool >= 1.0 or last_is_fixer:
        n_status = "replenished"
    else:
        n_status = "neutral"

    heavy = sum(1 for c in crops if CROP_DATABASE[c]["n_demand"] == "high")

    notes = []
    if heavy >= 2:
        notes.append(f"{heavy} of the last {len(crops)} crops were high-nitrogen feeders.")
    legumes = [c for c in crops if CROP_DATABASE[c]["n_demand"] == "fixer"]
    if legumes:
        notes.append(f"Nitrogen-fixing crop in history: {', '.join(legumes)}.")
    for fam, cnt in family_count.items():
        if cnt >= 2:
            notes.append(f"{fam} grown {cnt} times recently.")
    if water_pool >= 5.5:
        notes.append("Consistently high-water crops; check irrigation demand and drainage.")

    return {"crops": crops, "unknown": unknown, "last_crop": crops[-1] if crops else None,
            "n_pool": round(n_pool, 2), "n_status": n_status, "family_weight": family_weight,
            "heavy_n_count": heavy, "notes": notes}


# ---------- Scoring ----------
def _score_candidate(name: str, traits: dict, soil: dict, hist: dict) -> dict:
    BASE_SCORE = 60.0
    score = BASE_SCORE
    parts = {"rotation": 0.0, "nitrogen": 0.0, "soil_fit": 0.0, "carbon": 0.0, "water": 0.0}
    reasons = []
    cls = soil.get("classes", {})

    # Rotation: same-family penalty scales with how recently it was grown
    w = hist["family_weight"].get(traits["family"], 0)
    if w:
        parts["rotation"] -= 40 * w
        reasons.append(f"Same family ({traits['family']}) grown recently; disease and pest carryover risk.")
    if name == hist["last_crop"]:
        parts["rotation"] -= 15
        reasons.append("Same crop as the previous cycle.")

    # Nitrogen balance and fertilizer need
    need = N_NEED_BASE[traits["n_demand"]]
    if hist["n_status"] == "depleted":
        if traits["n_demand"] == "fixer":
            parts["nitrogen"] += 20
            reasons.append("Recent heavy nitrogen use; a nitrogen fixer helps restore the soil.")
        elif traits["n_demand"] == "high":
            parts["nitrogen"] -= 25
            reasons.append("Nitrogen likely drawn down by recent crops; this crop would need heavy fertilizer.")
        elif traits["n_demand"] == "moderate":
            parts["nitrogen"] -= 10
        if traits["n_demand"] != "fixer":
            need = min(3, need + 1)
    elif hist["n_status"] == "replenished" and traits["n_demand"] != "fixer":
        need = max(0, need - 1)
        if traits["n_demand"] == "high":
            parts["nitrogen"] += 10
            reasons.append("Recent legume nitrogen credit lowers fertilizer needs for this crop.")

    # Leaching risk: low CEC or coarse texture
    leaching = cls.get("cec") == "low" or soil.get("texture_name") in COARSE_TEXTURES
    fert_note = None
    if need >= 2 and leaching:
        parts["nitrogen"] -= 10
        fert_note = "Low nutrient retention (low CEC / coarse soil): split fertilizer applications to limit leaching."
        reasons.append(fert_note)

    # Soil fit: pH, salinity, texture
    ph, ec = soil.get("ph"), soil.get("salinity_ec_ds_m")
    if isinstance(ph, (int, float)):
        dist = max(traits["min_ph"] - ph, ph - traits["max_ph"], 0)
        if dist > 0:
            parts["soil_fit"] -= min(35, 20 * dist)
            reasons.append(f"Soil pH ({ph}) outside optimal range ({traits['min_ph']}-{traits['max_ph']}).")
    if isinstance(ec, (int, float)):
        over = ec - SALT_THRESHOLD_DS_M[traits["salt_tol"]]
        if over > 0:
            parts["soil_fit"] -= min(35, 15 * over)
            reasons.append(f"Salinity (EC {ec} dS/m) exceeds this crop's tolerance.")
        elif ec > 2.0 and traits["salt_tol"] == "tolerant":
            parts["soil_fit"] += 5
            reasons.append(f"Tolerates elevated salinity (EC {ec} dS/m).")
    if soil.get("texture_name") in traits["pref_textures"]:
        parts["soil_fit"] += 10
        reasons.append(f"Well suited to {soil['texture_name']} soil.")

    # Carbon: favor residue-returning crops where soil carbon is low or declining under business-as-usual
    carbon_class = cls.get("soc_t0") or cls.get("om")
    change = soil.get("soc_bau_change")
    declining = isinstance(change, (int, float)) and change < 0
    if (carbon_class == "low" or declining) and traits["soc_effect"]:
        boost = 1.5 if cls.get("rsr_ssm2") == "high" else 1.0
        if declining:
            boost += 0.5
        parts["carbon"] += 8 * traits["soc_effect"] * boost
        why = "Soil carbon is declining under current management" if declining else "Low soil carbon here"
        reasons.append(f"{why}; this crop returns organic matter."
                       + (" High sequestration potential at this location." if cls.get("rsr_ssm2") == "high" else ""))

    # Water: low available water capacity vs. thirsty crops
    if cls.get("awc") == "low":
        if traits["water_demand"] == "high":
            parts["water"] -= 15
            reasons.append("Low water-holding capacity; high-water crop risks stress and irrigation losses.")
        elif traits["water_demand"] == "moderate":
            parts["water"] -= 5

    raw = score + sum(parts.values())
    final = max(0, min(100, raw))
    return {"crop": name.title(), "role": traits["role"], "score": round(final), "raw_score": round(raw, 1),
            "fertilizer_need": FERT_LABEL[need], "fertilizer_note": fert_note,
            "breakdown": {k: round(v, 1) for k, v in parts.items()}, "reasons": reasons}


def evaluate_next_crops(past_3_crops: list[str], soil_profile: dict) -> list[dict]:
    if not soil_profile.get("in_central_valley", False):
        return [{"error": "Location is outside the Central Valley coverage area."}]
    hist = analyze_history(past_3_crops)
    scored = [_score_candidate(n, t, soil_profile, hist) for n, t in CROP_DATABASE.items()]
    def tie_key(c):
        t = CROP_DATABASE[c["crop"].lower()]
        return (-c["raw_score"], FERT_LABEL.index(c["fertilizer_need"]),
                WATER_LEVEL[t["water_demand"]], -t["soc_effect"])

    scored.sort(key=tie_key)
    return scored


# ---------- Single entry point for the website / chatbot ----------
_EXTRACTOR = None

def _get_extractor() -> SoilDataExtractor:
    global _EXTRACTOR
    if _EXTRACTOR is None:  # load rasters once per process, not per request
        _EXTRACTOR = SoilDataExtractor()
    return _EXTRACTOR


def recommend_next_crop(lat: float, lon: float, past_3_crops: list[str],
                        extractor: SoilDataExtractor | None = None, top_n: int = 5) -> dict:
    """past_3_crops ordered oldest -> newest. Returns a JSON-serializable dict."""
    extractor = extractor or _get_extractor()
    soil = extractor.get_soil_profile(lat, lon)
    hist = analyze_history(past_3_crops)
    warnings = []
    recs = evaluate_next_crops(past_3_crops, soil)[:top_n]
    if recs and "score" in recs[0] and recs[0]["score"] < 40:
        warnings.append("No crop is a strong fit here: soil pH or salinity limits every option. "
                        "A soil test and local advisor input are recommended.")
    if hist["unknown"]:
        warnings.append(f"Crops not in the database were ignored: {', '.join(hist['unknown'])}.")
    if extractor.missing_optional:
        warnings.append("Some data layers are not loaded yet: " + ", ".join(extractor.missing_optional))
    if soil.get("salinity_ec_ds_m") == 0:
        warnings.append("Salinity reads 0 dS/m, which may mean missing data rather than non-saline soil; verify locally.")

    return {"location": {"lat": lat, "lon": lon}, "soil_profile": soil,
            "history": hist, "recommendations": recs,
            "warnings": warnings}


if __name__ == "__main__":
    ex = SoilDataExtractor()
    result = recommend_next_crop(36.74, -119.79, ["tomatoes", "corn", "peppers"], extractor=ex)
    print(json.dumps(result, indent=2))
    ex.close()