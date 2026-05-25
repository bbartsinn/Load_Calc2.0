from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from services.calgary_form_pdf import (
    _conductor_parts,
    _draw_address,
    _draw_text,
    _fmt_amps,
    _fmt_number,
    _fmt_watts,
    _num,
    _service_demand_by_unit,
    _unit_component_values,
    _unit_lookup,
)


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / "city_of_edmonton_load_calculation.pdf"

UNIT_X = {
    "SFD": 308,
    "SS": 372,
    "LWH": 437,
}

BREAKER_X = {
    "SFD": 292,
    "SS": 356,
    "LWH": 421,
}

CONDUCTOR_X = {
    "SFD": 324,
    "SS": 388,
    "LWH": 453,
}


def _build_overlay(input_data, result_data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(612, 792))

    project = input_data.get("project", {})
    input_units = _unit_lookup(input_data.get("units"))
    result_units = _unit_lookup(result_data.get("units"))
    conductor_type = input_data.get("conductor_type", "Copper")

    _draw_address(c, 342, 678, project.get("sfd_address"), align="left")
    if "SS" in input_units:
        _draw_address(c, 322, 657, project.get("ss_address"), align="left")
    if "LWH" in input_units:
        _draw_address(c, 310, 636, project.get("lwh_address"), align="left")

    row_y = {
        "area_m2": 577,
        "basic_first_90": 550,
        "basic_additional": 523,
        "space_heating": 501,
        "air_conditioning": 480,
        "range": 457,
        "water_heaters": 425,
        "ev": 399,
        "additional": 367,
        "minimum": 355,
        "total": 326,
        "breaker": 318,
        "conductor": 318,
    }

    for unit, x in UNIT_X.items():
        if unit not in result_units:
            continue
        values = _unit_component_values(input_units.get(unit, {}), result_units[unit])
        _draw_text(c, x, row_y["area_m2"], _fmt_number(values["area_m2"], decimals=1), size=7.2, align="center")
        for key in [
            "basic_first_90",
            "basic_additional",
            "space_heating",
            "air_conditioning",
            "range",
            "water_heaters",
            "ev",
            "additional",
        ]:
            _draw_text(c, x, row_y[key], _fmt_watts(values[key]), size=7.2, align="center")
        _draw_text(c, x, row_y["minimum"], values["minimum"], size=7.2, align="center")
        _draw_text(c, x, row_y["total"], _fmt_watts(values["total"]), size=9, align="center", bold=True)
        _draw_text(c, BREAKER_X[unit], row_y["breaker"], values["breaker"].replace("A", ""), size=6.8, align="center")
        conductor_size, metal = _conductor_parts(values["conductor"], conductor_type)
        conductor_label = " ".join(part for part in [conductor_size, metal] if part)
        _draw_text(c, CONDUCTOR_X[unit], row_y["conductor"], conductor_label, size=4.4, align="center")

    demand_by_unit = _service_demand_by_unit(result_data)
    secondary_garden_demand = demand_by_unit.get("SS", 0) + demand_by_unit.get("LWH", 0)
    total_space_heat = sum(_num(unit.get("space_heating")) for unit in input_data.get("units", []))
    total_ac = sum(_num(unit.get("air_conditioning")) for unit in input_data.get("units", []))

    _draw_text(c, 420, 248, _fmt_watts(demand_by_unit.get("SFD", 0)), size=8.5)
    _draw_text(c, 420, 230, _fmt_watts(secondary_garden_demand), size=8.5)
    _draw_text(c, 420, 204, _fmt_watts(total_space_heat), size=8.5)
    _draw_text(c, 420, 184, _fmt_watts(total_ac), size=8.5)
    service_conductor_size, service_metal = _conductor_parts(
        result_data.get("Service Conductor Type and Size", ""),
        conductor_type,
    )
    service_conductor_label = " ".join(part for part in [service_conductor_size, service_metal] if part)
    _draw_text(c, 339, 177, _fmt_watts(result_data.get("Total Calculated Load (Watts)", 0)), size=9.5, bold=True)
    _draw_text(c, 405, 177, _fmt_amps(result_data.get("Total Amps", 0)), size=9.5, bold=True)
    _draw_text(c, 450, 178, service_conductor_label, size=4.8, align="left")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def build_city_of_edmonton_form_pdf(input_data, result_data):
    overlay = PdfReader(_build_overlay(input_data, result_data))
    writer = PdfWriter(clone_from=str(TEMPLATE_PATH))

    for index, page in enumerate(writer.pages):
        if index < len(overlay.pages):
            page.merge_page(overlay.pages[index])

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
