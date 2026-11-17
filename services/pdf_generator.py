from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _value(value):
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _table(rows, widths=None):
    cell = ParagraphStyle("Report cell", fontName="Helvetica", fontSize=9, leading=11)
    heading = ParagraphStyle("Report heading", parent=cell, fontName="Helvetica-Bold")
    wrapped = [
        [Paragraph(escape(str(value)).replace("\n", "<br/>"), heading if i == 0 else cell)
         for value in row]
        for i, row in enumerate(rows)
    ]
    table = Table(wrapped, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f3f5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172026")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2e8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


_UNIT_NAMES = {"SFD": "Single family dwelling", "SS": "Secondary suite", "LWH": "Laneway / backyard suite"}
_FIELD_LABELS = {
    "area_m2": "Living area used (m²)",
    "heating_cooling_interlocked": "Heating and cooling interlocked",
    "space_heating": "Space heating (W)",
    "air_conditioning": "Air conditioning (W)",
    "additional_load": "Additional fixed loads (W)",
    "ev_charging_watts": "EV charging (W)",
    "unit_conductor": "Conductor type and size",
    "unit_ocp": "Overcurrent protection",
    "unit_amps": "Calculated current (A)",
    "calculated_load": "Calculated demand (W)",
    "calculated_load_no_hvac": "Demand excluding heating and cooling (W)",
}


def _field_label(key):
    if key in _FIELD_LABELS:
        return _FIELD_LABELS[key]
    label = key.replace("_", " ").capitalize()
    for suffix, unit in ((" m2", "m²"), (" watts", "W")):
        if label.endswith(suffix):
            return f"{label[:-len(suffix)]} ({unit})"
    return label


def _unit_rows(unit):
    rows = [["Field", "Value"]]
    for key, value in unit.items():
        if key in ("unit_type", "breakdown"):
            continue
        if key == "area_summary" and isinstance(value, dict):
            for field, item in value.items():
                if field not in unit:
                    rows.append([_field_label(field), _value(item)])
        elif key == "additional_items" and isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    description = item.get("description") or "Additional equipment"
                    rows.append([f"{description} (W)", _value(item.get("watts"))])
        else:
            rows.append([_field_label(key), _value(value)])
    return rows


def _unit_name(unit):
    code = str(unit.get("unit_type") or "Unit")
    return escape(_UNIT_NAMES.get(code, code))


def _breakdown_rows(rows):
    output = [["Calculation", "Nameplate (W)", "Demand factor", "Included (W)"]]
    for row in rows or []:
        detail = row.get("rule", "")
        if row.get("note"):
            detail = f"{detail} - {row['note']}"
        output.append([
            f"{row.get('label', '')}\n{detail}",
            _value(row.get("nameplate_watts")),
            "Rule" if row.get("demand_percent") is None else f"{float(row.get('demand_percent')):.0f}%",
            _value(row.get("demand_watts")),
        ])
    return output


def build_calculation_pdf(calculation_data):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.55 * inch,
        title="Residential Electrical Load Estimate | Real World Electric",
        author="Real World Electric",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Residential Electrical Load Estimate", styles["Title"]),
        Paragraph("Real World Electric", styles["Heading2"]),
        Paragraph("Planning estimate from the residential electrical load calculator. Have the calculation reviewed before permit submission or service sizing.", styles["Normal"]),
        Spacer(1, 0.15 * inch),
    ]

    input_data = calculation_data.get("input", {})
    result_data = calculation_data.get("result", {})
    story.append(Paragraph(f"Service conductor: {_value(input_data.get('conductor_type'))}", styles["Normal"]))
    story.append(Spacer(1, 0.12 * inch))

    for unit in input_data.get("units", []):
        story.append(Paragraph(f"Inputs for {_unit_name(unit)}", styles["Heading3"]))
        story.append(_table(_unit_rows(unit), [2.6 * inch, 4.4 * inch]))
        story.append(Spacer(1, 0.12 * inch))

    for unit in result_data.get("units", []):
        story.append(Paragraph(f"Results for {_unit_name(unit)}", styles["Heading3"]))
        story.append(_table(_unit_rows(unit), [2.9 * inch, 4.1 * inch]))
        story.append(Spacer(1, 0.08 * inch))
        breakdown = _breakdown_rows(unit.get("breakdown", []))
        if len(breakdown) > 1:
            story.append(_table(breakdown, [3.2 * inch, 1.25 * inch, 1.0 * inch, 1.25 * inch]))
            story.append(Spacer(1, 0.12 * inch))

    story.append(Paragraph("Overall Totals", styles["Heading2"]))
    total_keys = [
        "Basic Demand Load (Watts)",
        "100% Towards Demand Load (Watts)",
        "Total Calculated Load (Watts)",
        "Total Amps",
        "Service OCP size (Amps)",
        "Service Conductor Type and Size",
    ]
    story.append(_table([["Field", "Value"]] + [[key, _value(result_data.get(key))] for key in total_keys], [3.3 * inch, 3.7 * inch]))
    story.append(Spacer(1, 0.12 * inch))

    service_breakdown = _breakdown_rows(result_data.get("Service Demand Breakdown", []))
    if len(service_breakdown) > 1:
        story.append(Paragraph("Service Demand Summary", styles["Heading2"]))
        story.append(_table(service_breakdown, [3.2 * inch, 1.25 * inch, 1.0 * inch, 1.25 * inch]))

    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph("Real World Electric | 403-808-2811 | info@realworldelectric.com", styles["Normal"]))
    doc.build(story)
    return buffer.getvalue()
