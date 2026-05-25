from io import BytesIO
from pathlib import Path
import re

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from services.calculation_engine import additional_loads, electric_range_load


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / "city_of_calgary_secondary_suite_load_calculation.pdf"


UNIT_X = {
    "SFD": 278,
    "SS": 382,
    "LWH": 486,
}


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def _fmt_number(value, decimals=0):
    number = _num(value)
    if decimals:
        text = f"{number:,.{decimals}f}".rstrip("0").rstrip(".")
    else:
        text = f"{number:,.0f}"
    return text


def _fmt_watts(value):
    return _fmt_number(value)


def _fmt_amps(value):
    return f"{_num(value):.1f}".rstrip("0").rstrip(".")


def _unit_lookup(items):
    return {item.get("unit_type"): item for item in items or []}


def _conductor_parts(text, fallback_type):
    match = re.match(r"([^,]+),\s*([A-Za-z]+)", text or "")
    if match:
        size = match.group(1).strip()
        metal = match.group(2).strip().lower()
    else:
        size = ""
        metal = (fallback_type or "").lower()
    return size, "Cu" if metal.startswith("copper") else "Al" if metal.startswith("aluminum") else ""


def _draw_text(c, x, y, text, size=8, align="right", bold=False):
    if text is None or text == "":
        return
    font = "Helvetica-Bold" if bold else "Helvetica"
    c.setFont(font, size)
    if align == "right":
        c.drawRightString(x, y, str(text))
    elif align == "center":
        c.drawCentredString(x, y, str(text))
    else:
        c.drawString(x, y, str(text))


def _draw_address(c, x, y, text, width=240, align="center"):
    if not text:
        return
    value = str(text).strip()
    c.setFont("Helvetica", 8)
    if align == "center":
        c.drawCentredString(x, y, value[:72])
    elif align == "right":
        c.drawRightString(x, y, value[:72])
    else:
        c.drawString(x, y, value[:72])


def _selected_suite_ep(project, input_units):
    unit_types = {unit.get("unit_type") for unit in input_units or []}
    values = []
    if "SS" in unit_types and project.get("ss_ep"):
        values.append(str(project.get("ss_ep")).strip())
    if "LWH" in unit_types and project.get("lwh_ep"):
        values.append(str(project.get("lwh_ep")).strip())
    return " / ".join(values)


def _unit_component_values(input_unit, result_unit):
    area_watts = result_unit.get("area_summary", {}).get("basic_area_watts", 0)
    first_area = 5000 if _num(result_unit.get("area_m2")) > 0 else 0
    additional_area = max(0, _num(area_watts) - first_area)
    range_watts = _num(input_unit.get("range_watts"))
    additional_load = _num(input_unit.get("additional_load"))
    has_range = range_watts > 0

    return {
        "area_m2": result_unit.get("area_m2", 0),
        "basic_first_90": first_area,
        "basic_additional": additional_area,
        "space_heating": input_unit.get("space_heating", 0),
        "air_conditioning": input_unit.get("air_conditioning", 0),
        "range": electric_range_load(range_watts),
        "water_heaters": (
            _num(input_unit.get("tankless_watts"))
            + _num(input_unit.get("steamer_watts"))
            + _num(input_unit.get("pool_hot_tub_watts"))
        ),
        "ev": input_unit.get("ev_charging_watts", 0),
        "additional": additional_loads(additional_load, has_range=has_range),
        "minimum": result_unit.get("unit_ocp", ""),
        "total": result_unit.get("calculated_load", 0),
        "breaker": result_unit.get("unit_ocp", ""),
        "conductor": result_unit.get("unit_conductor", ""),
    }


def _service_demand_by_unit(result_data):
    values = {}
    for row in result_data.get("Service Demand Breakdown", []):
        label = row.get("label", "")
        for unit in UNIT_X:
            if label.startswith(f"{unit} "):
                values[unit] = row.get("demand_watts", 0)
    return values


def _build_overlay(input_data, result_data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(612, 792))

    project = input_data.get("project", {})
    input_units_list = input_data.get("units", [])
    input_unit_types = {unit.get("unit_type") for unit in input_units_list}

    _draw_text(c, 486, 720, str(project.get("sfd_ep") or "")[:42], size=9, align="left", bold=True)
    _draw_text(c, 486, 697, _selected_suite_ep(project, input_units_list)[:42], size=9, align="left", bold=True)
    _draw_address(c, 275, 607, project.get("sfd_address"), align="left")
    if "SS" in input_unit_types:
        _draw_address(c, 176, 568, project.get("ss_address"))
    if "LWH" in input_unit_types:
        _draw_address(c, 468, 568, project.get("lwh_address"))

    input_units = _unit_lookup(input_data.get("units"))
    result_units = _unit_lookup(result_data.get("units"))
    conductor_type = input_data.get("conductor_type", "Copper")

    row_y = {
        "area_m2": 524,
        "basic_first_90": 495,
        "basic_additional": 466,
        "space_heating": 445,
        "air_conditioning": 424,
        "range": 405,
        "water_heaters": 377,
        "ev": 350,
        "additional": 308,
        "minimum": 269,
        "total": 238,
        "breaker": 205,
        "conductor": 217,
    }

    for unit, x in UNIT_X.items():
        if unit not in result_units:
            continue
        values = _unit_component_values(input_units.get(unit, {}), result_units[unit])
        _draw_text(c, x, row_y["area_m2"], _fmt_number(values["area_m2"], decimals=1), size=8)
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
            _draw_text(c, x, row_y[key], _fmt_watts(values[key]), size=8)
        _draw_text(c, x, row_y["minimum"], values["minimum"], size=8)
        _draw_text(c, x - 8, row_y["total"], _fmt_watts(values["total"]), size=10, bold=True)
        _draw_text(c, x - 55, row_y["breaker"], values["breaker"].replace("A", ""), size=8)
        conductor_size, metal = _conductor_parts(values["conductor"], conductor_type)
        conductor_label = " ".join(part for part in [conductor_size, metal] if part)
        _draw_text(c, x - 2, row_y["conductor"], conductor_label, size=6.5, align="center")

    demand_by_unit = _service_demand_by_unit(result_data)
    total_space_heat = sum(_num(unit.get("space_heating")) for unit in input_data.get("units", []))
    total_ac = sum(_num(unit.get("air_conditioning")) for unit in input_data.get("units", []))
    _draw_text(c, 420, 166, _fmt_watts(demand_by_unit.get("SFD", 0)), size=9)
    _draw_text(c, 420, 149, _fmt_watts(demand_by_unit.get("LWH", 0)), size=9)
    _draw_text(c, 420, 132, _fmt_watts(demand_by_unit.get("SS", 0)), size=9)
    _draw_text(c, 420, 108, _fmt_watts(total_space_heat), size=9)
    _draw_text(c, 420, 83, _fmt_watts(total_ac), size=9)
    _draw_text(c, 236, 56, _fmt_watts(result_data.get("Total Calculated Load (Watts)", 0)), size=11, bold=True)
    _draw_text(c, 306, 56, _fmt_amps(result_data.get("Total Amps", 0)), size=12, bold=True)
    _draw_text(c, 357, 53, result_data.get("Service Conductor Type and Size", ""), size=5.5, align="left")
    c.showPage()

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def build_city_of_calgary_form_pdf(input_data, result_data):
    overlay = PdfReader(_build_overlay(input_data, result_data))
    writer = PdfWriter(clone_from=str(TEMPLATE_PATH))

    for index, page in enumerate(writer.pages):
        if index < len(overlay.pages):
            page.merge_page(overlay.pages[index])

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
