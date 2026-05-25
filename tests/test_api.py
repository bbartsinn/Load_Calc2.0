import unittest
from unittest.mock import patch

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

    def test_calculate_counts_below_ground_area_at_75_percent(self):
        response = self.client.post("/api/calculate", json={
            "conductor_type": "Copper",
            "units": [{
                "unit_type": "SFD",
                "above_ground_m2": 90,
                "below_ground_m2": 100,
            }],
        })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["units"][0]["above_ground_m2"], 90)
        self.assertEqual(payload["units"][0]["below_ground_m2"], 100)
        self.assertEqual(payload["units"][0]["area_m2"], 165)
        self.assertEqual(payload["units"][0]["breakdown"][0]["demand_watts"], 6000)

    def test_basic_area_uses_started_90_m2_blocks(self):
        cases = [
            (90, 5000),
            (91, 6000),
            (120, 6000),
            (150, 6000),
            (180, 6000),
            (181, 7000),
            (200, 7000),
        ]

        for area_m2, expected_watts in cases:
            with self.subTest(area_m2=area_m2):
                response = self.client.post("/api/calculate", json={
                    "conductor_type": "Copper",
                    "units": [{
                        "unit_type": "SFD",
                        "area_m2": area_m2,
                    }],
                })

                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertEqual(payload["units"][0]["breakdown"][0]["demand_watts"], expected_watts)

    def test_calculate_shows_area_summary_watts(self):
        response = self.client.post("/api/calculate", json={
            "conductor_type": "Copper",
            "units": [{
                "unit_type": "SFD",
                "above_ground_m2": 90,
                "below_ground_m2": 90,
            }],
        })

        self.assertEqual(response.status_code, 200)
        summary = response.get_json()["units"][0]["area_summary"]
        self.assertEqual(summary["above_ground_m2"], 90)
        self.assertEqual(summary["below_ground_m2"], 90)
        self.assertEqual(summary["below_ground_counted_m2"], 67.5)
        self.assertEqual(summary["above_ground_watts"], 5000)
        self.assertEqual(summary["below_ground_watts"], 1000)
        self.assertEqual(summary["basic_area_watts"], 6000)

    def test_service_keeps_tankless_steamer_pool_and_ev_at_100_percent(self):
        response = self.client.post("/api/calculate", json={
            "conductor_type": "Copper",
            "units": [
                {
                    "unit_type": "SFD",
                    "area_m2": 90,
                    "tankless_watts": 2000,
                    "steamer_watts": 2000,
                    "pool_hot_tub_watts": 2000,
                    "ev_charging_watts": 2000,
                },
                {
                    "unit_type": "SS",
                    "area_m2": 90,
                    "tankless_watts": 2000,
                    "steamer_watts": 2000,
                    "pool_hot_tub_watts": 2000,
                    "ev_charging_watts": 2000,
                },
            ],
        })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["Basic Demand Load (Watts)"], 8250)
        self.assertEqual(payload["100% Towards Demand Load (Watts)"], 16000)
        self.assertEqual(payload["Total Calculated Load (Watts)"], 24250)

    def test_calculate_preserves_exact_watt_inputs(self):
        response = self.client.post("/api/calculate", json={
            "conductor_type": "Copper",
            "units": [{
                "unit_type": "SFD",
                "pool_hot_tub_watts": 5730,
            }],
        })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["units"][0]["calculated_load"], 5730)
        self.assertEqual(payload["units"][0]["breakdown"][0]["nameplate_watts"], 5730)
        self.assertEqual(payload["units"][0]["breakdown"][0]["demand_watts"], 5730)

    def test_city_form_pdf_generates_official_pdf(self):
        response = self.client.post("/api/city_form_pdf", json={
            "conductor_type": "Copper",
            "project": {
                "sfd_address": "123 Main St",
                "ss_address": "Basement Suite",
            },
            "units": [{
                "unit_type": "SFD",
                "above_ground_m2": 90,
                "below_ground_m2": 90,
                "range_watts": 6000,
            }],
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/pdf")
        self.assertGreater(len(response.data), 100000)
        self.assertTrue(response.data.startswith(b"%PDF"))

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

    def test_email_endpoint_generates_pdf_before_mailgun_config_check(self):
        with patch.dict("os.environ", {"MAILGUN_DOMAIN": "", "MAILGUN_API_KEY": ""}):
            response = self.client.post("/api/send_calculation_email", json={
                "userEmail": "owner@example.com",
                "inputData": {
                    "conductor_type": "Copper",
                    "units": [{"unit_type": "SFD", "area_m2": 90, "range_watts": 12000}],
                },
                "resultData": {},
            })

        self.assertEqual(response.status_code, 500)
        self.assertIn("Mailgun environment variables", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
