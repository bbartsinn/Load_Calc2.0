# calculation_engine.py

BELOW_GROUND_AREA_FACTOR = 0.75


def effective_living_area(above_ground_m2=0, below_ground_m2=0, fallback_area_m2=0):
    if above_ground_m2 or below_ground_m2:
        return above_ground_m2 + (below_ground_m2 * BELOW_GROUND_AREA_FACTOR)
    return fallback_area_m2


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
    # Single electric range: 6000 W, plus 40% of any nameplate amount over 12 kW.
    if range_watts <= 12000:
        return 6000
    else:
        return 6000 + 0.4 * (range_watts - 12000)

def electric_range_breakdown(range_watts):
    if range_watts <= 0:
        return []
    if range_watts <= 12000:
        return [{
            "label": "Single electric range",
            "rule": "CEC range demand",
            "nameplate_watts": range_watts,
            "demand_percent": None,
            "demand_watts": 6000,
            "note": "6,000 W minimum for one range up to 12 kW",
        }]
    excess = range_watts - 12000
    return [
        {
            "label": "Single electric range base",
            "rule": "CEC range demand",
            "nameplate_watts": 12000,
            "demand_percent": None,
            "demand_watts": 6000,
            "note": "6,000 W for first 12 kW",
        },
        {
            "label": "Single electric range excess",
            "rule": "CEC range demand",
            "nameplate_watts": excess,
            "demand_percent": 40,
            "demand_watts": 0.4 * excess,
            "note": "40% of nameplate over 12 kW",
        },
    ]

def additional_loads(load_watts, has_range=True):
    # Loads over 1500 W not otherwise captured above, such as dryers,
    # storage-tank water heaters, and large appliances.
    # If range present: 25% of the combined additional load.
    # If no range: 100% up to 6000 W + 25% above 6000 W.
    if has_range:
        return 0.25 * load_watts
    else:
        base = min(load_watts, 6000)
        extra = max(0, load_watts - 6000)
        return base + 0.25 * extra

def additional_load_breakdown(load_watts, has_range=True):
    if load_watts <= 0:
        return []
    if has_range:
        return [{
            "label": "Additional fixed loads over 1500 W",
            "rule": "Additional load demand with electric range",
            "nameplate_watts": load_watts,
            "demand_percent": 25,
            "demand_watts": 0.25 * load_watts,
            "note": "25% because an electric range is included",
        }]
    base = min(load_watts, 6000)
    extra = max(0, load_watts - 6000)
    rows = []
    if base:
        rows.append({
            "label": "Additional fixed loads base",
            "rule": "Additional load demand without electric range",
            "nameplate_watts": base,
            "demand_percent": 100,
            "demand_watts": base,
            "note": "First 6,000 W at 100%",
        })
    if extra:
        rows.append({
            "label": "Additional fixed loads balance",
            "rule": "Additional load demand without electric range",
            "nameplate_watts": extra,
            "demand_percent": 25,
            "demand_watts": 0.25 * extra,
            "note": "Balance over 6,000 W at 25%",
        })
    return rows

def unit_demand_breakdown(
    area_m2,
    space_heating=0,
    air_conditioning=0,
    interlocked=False,
    range_watts=0,
    additional_load=0,
    tankless_watts=0,
    steamer_watts=0,
    pool_hot_tub_watts=0,
    ev_charging_watts=0
):
    rows = []
    base = basic_load(area_m2)
    if base:
        rows.append({
            "label": "Basic area load",
            "rule": "5,000 W for first 90 m2, plus 1,000 W for each additional 90 m2 or portion",
            "nameplate_watts": None,
            "demand_percent": None,
            "demand_watts": base,
            "note": f"{area_m2:g} m2 living area",
        })

    if interlocked and (space_heating > 0 or air_conditioning > 0):
        selected = max(space_heating, air_conditioning)
        rows.append({
            "label": "Interlocked heat / AC",
            "rule": "Larger interlocked load only",
            "nameplate_watts": selected,
            "demand_percent": 100,
            "demand_watts": selected,
            "note": "Heating and cooling are interlocked",
        })
    else:
        if space_heating:
            rows.append({
                "label": "Space heating",
                "rule": "Space heating at 100%",
                "nameplate_watts": space_heating,
                "demand_percent": 100,
                "demand_watts": space_heating,
                "note": "",
            })
        if air_conditioning:
            rows.append({
                "label": "Air conditioning",
                "rule": "Air conditioning at 100%",
                "nameplate_watts": air_conditioning,
                "demand_percent": 100,
                "demand_watts": air_conditioning,
                "note": "",
            })

    rows.extend(electric_range_breakdown(range_watts))

    for label, watts, note in [
        ("Tankless electric water heater", tankless_watts, "Tankless water heater at 100%"),
        ("Steamer", steamer_watts, "Steamer water heater at 100%"),
        ("Pool / hot tub / spa", pool_hot_tub_watts, "Whole nameplate at 100%"),
        ("EV charging equipment", ev_charging_watts, "EVSE at 100%"),
    ]:
        if watts:
            rows.append({
                "label": label,
                "rule": note,
                "nameplate_watts": watts,
                "demand_percent": 100,
                "demand_watts": watts,
                "note": "",
            })

    rows.extend(additional_load_breakdown(additional_load, has_range=(range_watts > 0)))
    return rows

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

    # Handle interlocked heating/cooling by counting the larger load once.
    if interlocked:
        heating = max(space_heating, air_conditioning)
        ac = 0
    else:
        # Not interlocked, take both at 100%
        heating = space_heating_load(space_heating)
        ac = air_conditioning_load(air_conditioning)

    range_load = electric_range_load(range_watts)
    additional = additional_loads(additional_load, has_range=(range_watts > 0))

    # Electric tankless water heaters, steamers, pool/hot tub/spa water heaters,
    # and EV charging equipment are taken at 100%.
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
    # BASIC demand is the portion that can be demand-factored at the service.
    # Loads that must always stay at 100% are intentionally excluded here and
    # added back after the BASIC demand calculation.
    if area_m2 <= 0 and range_watts <= 0 and additional_load <= 0:
        return 0

    base = basic_load(area_m2)
    range_load = electric_range_load(range_watts)
    additional = additional_loads(additional_load, has_range=(range_watts > 0))

    return base + range_load + additional

def combined_load(units):
    """
    Calculates the combined no-HVAC load for multiple dwelling units using
    Rule 8-202(3)(a) demand tiers referenced by CEC Rule 8-200(2).
    Excludes HVAC loads during the initial calculation.
    """
    unit_loads_no_hvac = sorted(
        [u["calculated_load_no_hvac"] for u in units if u["calculated_load_no_hvac"] > 0],
        reverse=True
    )

    tiers = [
        (1, 1.00),
        (2, 0.65),
        (2, 0.40),
        (15, 0.25),
        (float("inf"), 0.10),
    ]

    total_combined_load_no_hvac = 0
    index = 0
    for count, factor in tiers:
        selected = unit_loads_no_hvac[index:index + int(count)] if count != float("inf") else unit_loads_no_hvac[index:]
        total_combined_load_no_hvac += sum(selected) * factor
        index += len(selected)
        if index >= len(unit_loads_no_hvac):
            break

    return total_combined_load_no_hvac

COPPER_TABLE = [
    ("#14", 20),
    ("#12", 25),
    ("#10", 35),
    ("#8", 50),
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
    ("600 kcmil", 420),
    ("700 kcmil", 460),
    ("750 kcmil", 475),
    ("800 kcmil", 490),
    ("900 kcmil", 520),
    ("1000 kcmil", 545),
    ("1250 kcmil", 590),
    ("1500 kcmil", 625),
    ("1750 kcmil", 650),
    ("2000 kcmil", 665),
]

ALUMINUM_TABLE = [
    ("#12", 20),
    ("#10", 30),
    ("#8", 40),
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
    ("600 kcmil", 340),
    ("700 kcmil", 375),
    ("750 kcmil", 385),
    ("800 kcmil", 395),
    ("900 kcmil", 425),
    ("1000 kcmil", 445),
    ("1250 kcmil", 485),
    ("1500 kcmil", 520),
    ("1750 kcmil", 545),
    ("2000 kcmil", 560),
]

STANDARD_OCP_SIZES = [60, 100, 125, 150, 200, 225, 250, 300, 350, 400, 500, 600]

def select_conductor_size(amps, conductor_type="copper"):
    conductor_type = conductor_type.lower()
    if conductor_type not in {"copper", "aluminum"}:
        raise ValueError("conductor_type must be Copper or Aluminum")
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
    unit_type = data.get("unit_type", "Unit")
    above_ground_m2 = data.get("above_ground_m2", 0)
    below_ground_m2 = data.get("below_ground_m2", 0)
    area_m2 = effective_living_area(
        above_ground_m2,
        below_ground_m2,
        data.get("area_m2", 0)
    )

    # Interlocked scenario
    interlocked = data.get("heating_cooling_interlocked", False)

    space_heating = data.get("space_heating", 0)
    air_conditioning = data.get("air_conditioning", 0)
    range_watts = data.get("range_watts", 0)

    # These loads are always at 100%.
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
    breakdown = unit_demand_breakdown(
        area_m2, space_heating, air_conditioning, interlocked,
        range_watts, additional_load, tankless_watts, steamer_watts, pool_hot_tub_watts, ev_charging_watts
    )
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
        "unit_type": unit_type,
        "above_ground_m2": above_ground_m2,
        "below_ground_m2": below_ground_m2,
        "area_m2": area_m2,
        "calculated_load": total,
        "calculated_load_no_hvac": total_no_hvac_val,
        "space_heating": space_heating,
        "air_conditioning": air_conditioning,
        "unit_amps": amps,
        "unit_ocp": ocp_label,
        "unit_conductor": conductor_desc,
        "breakdown": breakdown
    }

def calculate_service_parameters(final_combined_load, units, conductor_type="Copper"):
    """
    Determine the service OCP (if single unit) and service conductor sizing based on the scenario.
    For single-unit: size service conductor from the service OCP rating.
    For multi-unit: size service OCP from the final combined service amps.
    Size conductor from the service OCP when available. Minimum conductor size:
      - If Copper: no smaller than #3 (100A rating)
      - If Aluminum: no smaller than #1 (100A rating)
    """
    total_amps = final_combined_load / 240.0 if final_combined_load > 0 else 0
    conductor_type = conductor_type.capitalize()
    service_area = max([u.get("area_m2", 0) for u in units] or [0])
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
        service_ocp = select_ocp(total_amps, service_area)
        sizing_amps = service_ocp if service_ocp is not None else total_amps
        conductor_size_name, conductor_rating = select_conductor_size(sizing_amps, conductor_type)
        if conductor_size_name == "Larger than 500 kcmil":
            service_conductor = "Parallel runs required"
        else:
            # Enforce minimum sizes for multi-unit scenario
            if conductor_type.lower() == "copper" and conductor_rating < 100:
                conductor_size_name, conductor_rating = "#3", 100
            elif conductor_type.lower() == "aluminum" and conductor_rating < 100:
                conductor_size_name, conductor_rating = "#1", 100
            service_conductor = f"{conductor_size_name}, {conductor_type} (Rated {conductor_rating}A)"
        service_ocp_label = f"{service_ocp}A" if service_ocp is not None else None
        return service_ocp_label, service_conductor
