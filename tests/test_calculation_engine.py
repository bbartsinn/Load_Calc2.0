import unittest

from services.calculation_engine import (
    additional_loads,
    calculate_service_parameters,
    calculate_unit_loads,
    combined_load,
    electric_range_load,
    select_conductor_size,
    select_ocp,
    total_load,
)


class CalculationEngineTest(unittest.TestCase):
    def test_interlocked_equal_heat_and_ac_counts_once(self):
        load = total_load(
            area_m2=90,
            space_heating=5000,
            air_conditioning=5000,
            interlocked=True,
            range_watts=0,
        )

        self.assertEqual(load, 10000)

    def test_combined_load_applies_third_unit_demand(self):
        units = [
            {"calculated_load_no_hvac": 10000},
            {"calculated_load_no_hvac": 8000},
            {"calculated_load_no_hvac": 6000},
        ]

        self.assertEqual(combined_load(units), 19100)

    def test_unit_type_is_preserved_for_results(self):
        result = calculate_unit_loads({"unit_type": "SS", "area_m2": 90}, "Copper")

        self.assertEqual(result["unit_type"], "SS")

    def test_invalid_conductor_type_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_unit_loads({"area_m2": 90}, "Steel")

    def test_150_amp_service_size_is_available(self):
        self.assertEqual(select_ocp(130, 100), 150)

    def test_ev_charger_is_counted_at_full_nameplate(self):
        load = total_load(area_m2=0, ev_charging_watts=9600)

        self.assertEqual(load, 9600)

    def test_single_range_uses_cec_demand_rule(self):
        self.assertEqual(electric_range_load(12000), 6000)
        self.assertEqual(electric_range_load(17000), 8000)

    def test_additional_loads_use_range_dependent_demand(self):
        self.assertEqual(additional_loads(5500, has_range=True), 1375)
        self.assertEqual(additional_loads(8000, has_range=False), 6500)

    def test_hot_tub_is_counted_at_full_nameplate(self):
        load = total_load(area_m2=0, pool_hot_tub_watts=7500)

        self.assertEqual(load, 7500)

    def test_multi_unit_service_ocp_is_sized_from_combined_load(self):
        units = [
            calculate_unit_loads({"unit_type": "SFD", "area_m2": 200}, "Copper"),
            calculate_unit_loads({"unit_type": "SS", "area_m2": 500}, "Copper"),
        ]

        service_ocp, service_conductor = calculate_service_parameters(14550, units, "Copper")

        self.assertEqual(service_ocp, "100A")
        self.assertIn("#3, Copper", service_conductor)

    def test_conductor_tables_use_75_degree_values(self):
        self.assertEqual(select_conductor_size(200, "Copper"), ("3/0", 200))
        self.assertEqual(select_conductor_size(200, "Aluminum"), ("250 kcmil", 205))


if __name__ == "__main__":
    unittest.main()
