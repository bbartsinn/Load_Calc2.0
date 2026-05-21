import unittest

from app import app


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_calculate_accepts_valid_payload(self):
        response = self.client.post("/api/calculate", json={
            "conductor_type": "Copper",
            "units": [
                {
                    "unit_type": "SFD",
                    "area_m2": 90,
                    "range_watts": 12000,
                }
            ],
        })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["units"][0]["unit_type"], "SFD")
        self.assertGreater(payload["Total Amps"], 0)

    def test_calculate_rejects_invalid_conductor(self):
        response = self.client.post("/api/calculate", json={
            "conductor_type": "Steel",
            "units": [{"unit_type": "SFD", "area_m2": 90}],
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("conductor_type", response.get_json()["error"])

    def test_calculate_rejects_negative_load(self):
        response = self.client.post("/api/calculate", json={
            "conductor_type": "Copper",
            "units": [{"unit_type": "SFD", "area_m2": -1}],
        })

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
