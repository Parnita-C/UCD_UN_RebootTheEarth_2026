import unittest
from recommender_engine import SoilDataExtractor, evaluate_next_crops


class TestCropRecommendationEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize the extractor once for all tests."""
        cls.extractor = SoilDataExtractor()
        # Known coordinates
        cls.davis_lat, cls.davis_lon = 38.5449, -121.7405  # Inside Central Valley
        cls.fresno_lat, cls.fresno_lon = 36.7468, -119.7726  # Inside Central Valley (South)
        cls.sf_lat, cls.sf_lon = 37.7749, -122.4194  # Outside Central Valley

    # ---------------------------------------------------------------------------
    # 1. SPATIAL BOUNDARY & EXTRACTION TESTS
    # ---------------------------------------------------------------------------

    def test_davis_inside_central_valley(self):
        """Verify Davis, CA returns valid soil data inside Central Valley."""
        profile = self.extractor.get_soil_profile(self.davis_lat, self.davis_lon)
        self.assertTrue(profile["in_central_valley"])
        self.assertIsInstance(profile["organic_matter_kg_m2"], float)
        self.assertIsInstance(profile["ph"], float)
        self.assertIsInstance(profile["salinity_ec_ds_m"], float)
        self.assertIsNotNone(profile["texture_code"])

    def test_sf_outside_central_valley(self):
        """Verify San Francisco returns in_central_valley=False and N/A for all metrics."""
        profile = self.extractor.get_soil_profile(self.sf_lat, self.sf_lon)
        self.assertFalse(profile["in_central_valley"])
        self.assertEqual(profile["organic_matter_kg_m2"], "N/A")
        self.assertEqual(profile["ph"], "N/A")
        self.assertEqual(profile["salinity_ec_ds_m"], "N/A")
        self.assertEqual(profile["texture_name"], "N/A")

    def test_evaluate_crops_out_of_bounds_error(self):
        """Verify evaluating crops outside Central Valley returns an error dict."""
        sf_profile = self.extractor.get_soil_profile(self.sf_lat, self.sf_lon)
        results = evaluate_next_crops(["Tomatoes", "Corn", "Tomatoes"], sf_profile)
        self.assertEqual(len(results), 1)
        self.assertIn("error", results[0])

    # ---------------------------------------------------------------------------
    # 2. AGRONOMIC ROTATION & SCORING LOGIC TESTS
    # ---------------------------------------------------------------------------

    def test_nitrogen_depletion_recommends_legumes(self):
        """Consecutive heavy nitrogen feeders (Tomatoes, Corn) should favor Alfalfa/Beans."""
        profile = self.extractor.get_soil_profile(self.davis_lat, self.davis_lon)
        results = evaluate_next_crops(["Tomatoes", "Corn", "Tomatoes"], profile)

        top_crop = results[0]["crop"]
        self.assertIn(top_crop, ["Alfalfa", "Beans", "Wheat"])

        # Verify reason logged for top crop
        reasons_text = " ".join(results[0]["reasons"])
        self.assertIn("legume fixer strongly recommended", reasons_text)

    def test_family_rotation_disease_penalty(self):
        """Planting Tomatoes repeatedly should penalize Solanaceae crops (Tomatoes/Peppers)."""
        profile = self.extractor.get_soil_profile(self.davis_lat, self.davis_lon)
        results = evaluate_next_crops(["Tomatoes", "Peppers", "Tomatoes"], profile)

        # Find tomato entry
        tomato_entry = next(c for c in results if c["crop"] == "Tomatoes")
        reasons_text = " ".join(tomato_entry["reasons"])

        self.assertIn("high disease risk", reasons_text)

    def test_ph_penalty_applied(self):
        """Test that crops with narrow pH ranges get penalized if pH is out of bounds."""
        mock_profile = {
            "in_central_valley": True,
            "organic_matter_kg_m2": 15.0,
            "ph": 8.2,  # Alkaline soil
            "salinity_ec_ds_m": 0.5,
            "texture_code": 7,
            "texture_name": "Loam"
        }
        results = evaluate_next_crops(["Wheat", "Wheat", "Wheat"], mock_profile)

        # Peppers prefer pH 6.0-6.8, so pH 8.2 should trigger a penalty
        peppers_entry = next(c for c in results if c["crop"] == "Peppers")
        reasons_text = " ".join(peppers_entry["reasons"])
        self.assertIn("outside optimal range", reasons_text)

    def test_salinity_threshold_penalty(self):
        """High EC (salinity) should penalize salt-sensitive crops like Beans/Peppers."""
        mock_profile = {
            "in_central_valley": True,
            "organic_matter_kg_m2": 15.0,
            "ph": 6.5,
            "salinity_ec_ds_m": 3.5,  # High salinity
            "texture_code": 7,
            "texture_name": "Loam"
        }
        results = evaluate_next_crops(["Wheat", "Corn", "Wheat"], mock_profile)

        beans_entry = next(c for c in results if c["crop"] == "Beans")
        reasons_text = " ".join(beans_entry["reasons"])
        self.assertIn("exceeds sensitivity threshold", reasons_text)


if __name__ == "__main__":
    unittest.main()
