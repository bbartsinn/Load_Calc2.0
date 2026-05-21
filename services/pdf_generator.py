from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _value(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.1f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _table(rows, widths=None):
    table = Table(rows, colWidths=widths, repeatRows=1)
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


def _breakdown_rows(rows):
    output = [["Calculation", "Nameplate", "Demand", "Included"]]
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
        title="Real World Electric Load Calculation",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Real World Electric Load Calculation", styles["Title"]),
        Paragraph("City of Calgary Digital Load Calculator", styles["Heading2"]),
        Spacer(1, 0.15 * inch),
    ]

    input_data = calculation_data.get("input", {})
    result_data = calculation_data.get("result", {})
    story.append(Paragraph(f"Service conductor: {_value(input_data.get('conductor_type'))}", styles["Normal"]))
    story.append(Spacer(1, 0.12 * inch))

    for unit in input_data.get("units", []):
        story.append(Paragraph(f"Input Data - {_value(unit.get('unit_type', 'Unit'))}", styles["Heading3"]))
        rows = [["Field", "Value"]]
        for key, value in unit.items():
            rows.append([key, _value(value)])
        story.append(_table(rows, [2.6 * inch, 4.4 * inch]))
        story.append(Spacer(1, 0.12 * inch))

    for unit in result_data.get("units", []):
        story.append(Paragraph(f"Results - {_value(unit.get('unit_type', 'Unit'))}", styles["Heading3"]))
        rows = [["Field", "Value"]]
        for key, value in unit.items():
            if key != "breakdown":
                rows.append([key, _value(value)])
        story.append(_table(rows, [2.9 * inch, 4.1 * inch]))
        story.append(Spacer(1, 0.08 * inch))
        breakdown = _breakdown_rows(unit.get("breakdown", []))
        if len(breakdown) > 1:
            story.append(_table(breakdown, [3.2 * inch, 1.25 * inch, 1.0 * inch, 1.25 * inch]))
            story.append(Spacer(1, 0.12 * inch))

    story.append(Paragraph("Overall Totals", styles["Heading2"]))
    total_keys = [
        "Combined No-HVAC Load (Watts)",
        "Total HVAC Load (Watts)",
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
    story.append(Paragraph("Real World Electric | 403-808-2811 | Bart@Realworldelectric.com", styles["Normal"]))
    doc.build(story)
    return buffer.getvalue()
