# calculation_engine.py

def basic_load(area_m2):
    if area_m2 <= 0:
        return 0
    if area_m2 <= 90:
        return 5000
    additional_area = area_m2 - 90
    return 5000 + (1000 * ((additional_area + 89) // 90))  # round up per 90m²

def space_heating_load(load_watts):
    # Always 100%
    return load_watts

def air_conditioning_load(load_watts):
    # Always 100%
    return load_watts

def electric_range_load(range_watts):
    # If no range selected or 0, no load.
    if range_watts == 0:
        return 0
    # ≤12kW = 6000W, >12kW = 6000 + 40% above 12kW
    if range_watts <= 12000:
        return 6000
    else:
        return 6000 + 0.4 * (range_watts - 12000)

def additional_loads(load_watts, has_range=True):
    # If range present: 25% of (load_watts - 1500) if >1500W
    # If no range: 100% up to 6000W + 25% above 6000W
    if has_range:
        return 0.25 * max(0, load_watts - 1500)
    else:
        base = min(load_watts, 6000)
        extra = max(0, load_watts - 6000)
        return base + 0.25 * extra

def total_load(
    area_m2,
    space_heating=0,
    air_conditioning=0,
    interlocked=False,  # New parameter to handle interlock scenario
    range_watts=0,
    additional_load=0,
    tankless_watts=0,
    steamer_watts=0,
    pool_hot_tub_watts=0,
    ev_charging_watts=0
):
    # If no meaningful input:
    if (area_m2 <= 0 and space_heating <= 0 and air_conditioning <= 0 and range_watts <= 0
        and additional_load <= 0 and tankless_watts <= 0 and steamer_watts <= 0 
        and pool_hot_tub_watts <= 0 and ev_charging_watts <= 0):
        return 0

    base = basic_load(area_m2)

    # Handle interlocked scenario for heating/cooling:
    if interlocked:
        # Only take the greater of space heating or AC
        max_hvac = max(space_heating, air_conditioning)
        heating = max_hvac if max_hvac == space_heating else 0
        ac = max_hvac if max_hvac == air_conditioning else 0
    else:
        # Not interlocked, take both at 100%
        heating = space_heating_load(space_heating)
        ac = air_conditioning_load(air_conditioning)

    range_load = electric_range_load(range_watts)
    additional = additional_loads(additional_load, has_range=(range_watts > 0))

    # Tankless, Steamer, Pool/HotTub, EV always 100%
    tankless = tankless_watts
    steamer = steamer_watts
    pool_hot_tub = pool_hot_tub_watts
    ev = ev_charging_watts

    return base + heating + ac + range_load + tankless + steamer + pool_hot_tub + ev + additional

def total_load_no_hvac(
    area_m2,
    range_watts=0,
    additional_load=0,
    tankless_watts=0,
    steamer_watts=0,
    pool_hot_tub_watts=0,
    ev_charging_watts=0
):
    # No HVAC means we do not count space heating or AC here.
    # But tankless, steamer, pool/hot tub, EV are still included at 100%.
    if (area_m2 <= 0 and range_watts <= 0 and additional_load <= 0 and
        tankless_watts <= 0 and steamer_watts <= 0 and pool_hot_tub_watts <=0 and ev_charging_watts <=0):
        return 0

    base = basic_load(area_m2)
    range_load = electric_range_load(range_watts)
    additional = additional_loads(additional_load, has_range=(range_watts > 0))

    return base + range_load + additional + tankless_watts + steamer_watts + pool_hot_tub_watts + ev_charging_watts

def combined_load(units):
    """
    Calculates the combined load of multiple units per CEC Rule 8-200(2).
    Excludes HVAC loads during the initial calculation.
    """
    # Extract and sort the no-HVAC loads in descending order
    unit_loads_no_hvac = sorted(
        [u["calculated_load_no_hvac"] for u in units if u["calculated_load_no_hvac"] > 0],
        reverse=True
    )

    # Initialize combined load
    total_combined_load_no_hvac = 0

    # Apply percentages based on CEC Rule 8-200(2)
    if len(unit_loads_no_hvac) > 0:
        total_combined_load_no_hvac += unit_loads_no_hvac[0]  # 100% of the heaviest load
    if len(unit_loads_no_hvac) > 1:
        total_combined_load_no_hvac += unit_loads_no_hvac[1] * 0.65  # 65% of the second heaviest load

    # Return the combined load without HVAC
    return total_combined_load_no_hvac

COPPER_TABLE = [
    ("#6", 65),
    ("#4", 85),
    ("#3", 100),
    ("#2", 115),
    ("#1", 130),
    ("1/0", 150),
    ("2/0", 175),
    ("3/0", 200),
    ("4/0", 230),
    ("250 kcmil", 255),
    ("300 kcmil", 285),
    ("350 kcmil", 310),
    ("400 kcmil", 335),
    ("500 kcmil", 380),
]

ALUMINUM_TABLE = [
    ("#6", 50),
    ("#4", 65),
    ("#3", 75),
    ("#2", 90),
    ("#1", 100),
    ("1/0", 120),
    ("2/0", 135),
    ("3/0", 155),
    ("4/0", 180),
    ("250 kcmil", 205),
    ("300 kcmil", 230),
    ("350 kcmil", 250),
    ("400 kcmil", 270),
    ("500 kcmil", 310),
]

STANDARD_OCP_SIZES = [60, 100, 125, 200]

def select_conductor_size(amps, conductor_type="copper"):
    conductor_type = conductor_type.lower()
    table = COPPER_TABLE if conductor_type == "copper" else ALUMINUM_TABLE
    for size, rating in table:
        if rating >= amps:
            return size, rating
    return "Larger than 500 kcmil", None

def select_ocp(amps, area_m2):
    if area_m2 <= 0 and amps <= 0:
        return None
    min_required = 100 if area_m2 >= 80 else 60
    required = max(min_required, amps)
    for size in STANDARD_OCP_SIZES:
        if size >= required:
            return size
    return None

def calculate_unit_loads(data, conductor_type="Copper"):
    area_m2 = data.get("area_m2", 0)

    # Interlocked scenario
    interlocked = data.get("heating_cooling_interlocked", False)

    space_heating = data.get("space_heating", 0)
    air_conditioning = data.get("air_conditioning", 0)
    range_watts = round(data.get("range_watts", 0))

    # These loads are always at 100%
    tankless_watts = data.get("tankless_watts", 0)
    steamer_watts = data.get("steamer_watts", 0)
    pool_hot_tub_watts = data.get("pool_hot_tub_watts", 0)
    ev_charging_watts = data.get("ev_charging_watts", 0)

    additional_load = data.get("additional_load", 0)

    # Check if no meaningful load:
    if (area_m2 <= 0 and space_heating <= 0 and air_conditioning <= 0 and range_watts <= 0
        and additional_load <= 0 and tankless_watts <= 0 and steamer_watts <=0
        and pool_hot_tub_watts <=0 and ev_charging_watts<=0):
        return None

    total = total_load(
        area_m2, space_heating, air_conditioning, interlocked,
        range_watts, additional_load, tankless_watts, steamer_watts, pool_hot_tub_watts, ev_charging_watts
    )
    if total <= 0:
        return None

    total_no_hvac_val = total_load_no_hvac(area_m2, range_watts, additional_load,
                                           tankless_watts, steamer_watts, pool_hot_tub_watts, ev_charging_watts)
    amps = total / 240.0
    ocp = select_ocp(amps, area_m2)

    conductor_desc = "Cannot size from standard tables"
    if ocp is None:
        ocp_label = "Exceeds standard 200A"
    else:
        ocp_label = f"{ocp}A"
        conductor_size_name, conductor_rating = select_conductor_size(ocp, conductor_type)
        if conductor_size_name == "Larger than 500 kcmil":
            conductor_desc = "Parallel runs required"
        else:
            conductor_desc = f"{conductor_size_name}, {conductor_type.capitalize()} (Rated {conductor_rating}A)"

    return {
        "area_m2": area_m2,
        "calculated_load": total,
        "calculated_load_no_hvac": total_no_hvac_val,
        "space_heating": space_heating,
        "air_conditioning": air_conditioning,
        "unit_amps": amps,
        "unit_ocp": ocp_label,
        "unit_conductor": conductor_desc
    }

def calculate_service_parameters(final_combined_load, units, conductor_type="Copper"):
    """
    Determine the service OCP (if single unit) and service conductor sizing based on the scenario.
    For single-unit: size service conductor from the service OCP rating.
    For multi-unit: no service OCP, size conductor from load amps. Minimum conductor size:
      - If Copper: no smaller than #3 (100A rating)
      - If Aluminum: no smaller than #1 (100A rating)
    """
    total_amps = final_combined_load / 240.0 if final_combined_load > 0 else 0
    conductor_type = conductor_type.capitalize()
    if len(units) == 1:
        unit_ocp_label = units[0].get("unit_ocp")
        if unit_ocp_label and unit_ocp_label.endswith("A"):
            ocp_value = int(unit_ocp_label[:-1])
            conductor_size_name, conductor_rating = select_conductor_size(ocp_value, conductor_type)
            if conductor_size_name == "Larger than 500 kcmil":
                service_conductor = "Parallel runs required"
            else:
                service_conductor = f"{conductor_size_name}, {conductor_type} (Rated {conductor_rating}A)"
            return unit_ocp_label, service_conductor
        else:
            return None, "Cannot size from standard tables"
    else:
        conductor_size_name, conductor_rating = select_conductor_size(total_amps, conductor_type)
        if conductor_size_name == "Larger than 500 kcmil":
            service_conductor = "Parallel runs required"
        else:
            # Enforce minimum sizes for multi-unit scenario
            if conductor_type.lower() == "copper" and conductor_rating < 100:
                conductor_size_name, conductor_rating = "#3", 100
            elif conductor_type.lower() == "aluminum" and conductor_rating < 100:
                conductor_size_name, conductor_rating = "#1", 100
            service_conductor = f"{conductor_size_name}, {conductor_type} (Rated {conductor_rating}A)"
        return None, service_conductor
