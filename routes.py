# routes.py
from flask import Blueprint, request, jsonify, render_template, send_file
from io import BytesIO
import requests
import os
import json
import logging
import re
from html import escape

from services.calculation_engine import (
    calculate_unit_loads,
    combined_load,
    calculate_service_parameters,
    effective_living_area
)
from services.email_template import build_branded_email
from services.pdf_generator import build_calculation_pdf
from services.calgary_form_pdf import build_city_of_calgary_form_pdf
from services.edmonton_form_pdf import build_city_of_edmonton_form_pdf

api = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

VALID_CONDUCTOR_TYPES = {"Copper", "Aluminum"}
VALID_CITY_FORMS = {"calgary", "edmonton"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _number(value, field_name):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number")
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return number


def normalize_calculation_input(data):
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")

    conductor_type = data.get("conductor_type", "Copper")
    if conductor_type not in VALID_CONDUCTOR_TYPES:
        raise ValueError("conductor_type must be Copper or Aluminum")

    raw_units = data.get("units", [])
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError("At least one unit is required")

    units = []
    for index, unit in enumerate(raw_units, start=1):
        if not isinstance(unit, dict):
            raise ValueError(f"Unit {index} must be an object")
        above_ground_m2 = _number(unit.get("above_ground_m2"), f"Unit {index} above_ground_m2")
        below_ground_m2 = _number(unit.get("below_ground_m2"), f"Unit {index} below_ground_m2")
        area_m2 = _number(unit.get("area_m2"), f"Unit {index} area_m2")
        if above_ground_m2 or below_ground_m2:
            area_m2 = effective_living_area(above_ground_m2, below_ground_m2, area_m2)
        units.append({
            "unit_type": str(unit.get("unit_type") or f"Unit {index}")[:40],
            "above_ground_m2": above_ground_m2,
            "below_ground_m2": below_ground_m2,
            "area_m2": area_m2,
            "space_heating": _number(unit.get("space_heating"), f"Unit {index} space_heating"),
            "air_conditioning": _number(unit.get("air_conditioning"), f"Unit {index} air_conditioning"),
            "heating_cooling_interlocked": bool(unit.get("heating_cooling_interlocked", False)),
            "range_watts": _number(unit.get("range_watts"), f"Unit {index} range_watts"),
            "additional_load": _number(unit.get("additional_load"), f"Unit {index} additional_load"),
            "tankless_watts": _number(unit.get("tankless_watts"), f"Unit {index} tankless_watts"),
            "steamer_watts": _number(unit.get("steamer_watts"), f"Unit {index} steamer_watts"),
            "pool_hot_tub_watts": _number(unit.get("pool_hot_tub_watts"), f"Unit {index} pool_hot_tub_watts"),
            "ev_charging_watts": _number(unit.get("ev_charging_watts"), f"Unit {index} ev_charging_watts"),
            "additional_items": unit.get("additional_items", []),
        })

    project = data.get("project", {})
    if not isinstance(project, dict):
        project = {}

    unit_types = {unit["unit_type"] for unit in units}

    return {
        "num_units": len(units),
        "conductor_type": conductor_type,
        "project": {
            "sfd_address": str(project.get("sfd_address") or "")[:160],
            "sfd_ep": str(project.get("sfd_ep") or "")[:60],
            "ss_address": str(project.get("ss_address") or "")[:160] if "SS" in unit_types else "",
            "ss_ep": str(project.get("ss_ep") or "")[:60] if "SS" in unit_types else "",
            "lwh_address": str(project.get("lwh_address") or "")[:160] if "LWH" in unit_types else "",
            "lwh_ep": str(project.get("lwh_ep") or "")[:60] if "LWH" in unit_types else "",
        },
        "units": units,
    }


def run_calculation(input_data):
    conductor_type = input_data["conductor_type"]
    units_data = []
    for unit in input_data["units"]:
        result = calculate_unit_loads(unit, conductor_type)
        if result:
            units_data.append(result)

    if not units_data:
        raise ValueError("No valid load-bearing units provided")

    combined_no_hvac = combined_load(units_data)
    total_hvac_load = sum(u["calculated_load"] - u["calculated_load_no_hvac"] for u in units_data)
    final_combined_load = combined_no_hvac + total_hvac_load

    service_ocp_label, service_conductor_desc = calculate_service_parameters(
        final_combined_load,
        units_data,
        conductor_type
    )

    service_breakdown = build_service_breakdown(units_data, combined_no_hvac, total_hvac_load)

    return {
        "units": units_data,
        "Basic Demand Load (Watts)": combined_no_hvac,
        "100% Towards Demand Load (Watts)": total_hvac_load,
        "Total Calculated Load (Watts)": final_combined_load,
        "Total Amps": final_combined_load / 240.0,
        "Service OCP size (Amps)": service_ocp_label,
        "Service Conductor Type and Size": service_conductor_desc,
        "Service Demand Breakdown": service_breakdown
    }


def build_service_breakdown(units_data, combined_no_hvac, total_hvac_load):
    sorted_units = sorted(
        [u for u in units_data if u["calculated_load_no_hvac"] > 0],
        key=lambda unit: unit["calculated_load_no_hvac"],
        reverse=True
    )
    tiers = [
        (1, 100, "Largest unit BASIC demand"),
        (2, 65, "Next two unit BASIC demand loads"),
        (2, 40, "Next two unit BASIC demand loads"),
        (15, 25, "Next fifteen unit BASIC demand loads"),
        (float("inf"), 10, "Remaining unit BASIC demand loads"),
    ]

    rows = []
    index = 0
    for count, percent, label in tiers:
        selected = sorted_units[index:] if count == float("inf") else sorted_units[index:index + int(count)]
        if not selected:
            continue
        for unit in selected:
            nameplate = unit["calculated_load_no_hvac"]
            rows.append({
                "label": f"{unit.get('unit_type', 'Unit')} BASIC demand",
                "rule": label,
                "nameplate_watts": nameplate,
                "demand_percent": percent,
                "demand_watts": nameplate * (percent / 100),
                "note": "100% demand loads excluded at this step",
            })
        index += len(selected)

    if total_hvac_load:
        rows.append({
            "label": "100% Towards Demand load",
            "rule": "Add after BASIC demand calculation",
            "nameplate_watts": total_hvac_load,
            "demand_percent": 100,
            "demand_watts": total_hvac_load,
            "note": "Includes interlock selections per unit",
        })

    rows.append({
        "label": "Final service demand",
        "rule": "BASIC demand plus 100% towards demand load",
        "nameplate_watts": None,
        "demand_percent": None,
        "demand_watts": combined_no_hvac + total_hvac_load,
        "note": "",
    })
    return rows

# -------------------------------------------------------
# /calculate - Perform load calculation
# -------------------------------------------------------
@api.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No input data provided"}), 400

    try:
        input_data = normalize_calculation_input(data)
        return jsonify(run_calculation(input_data)), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Calculation failed")
        return jsonify({"error": "Calculation failed. Please check your inputs and try again."}), 500


@api.route('/city_form_pdf', methods=['POST'])
def city_form_pdf():
    data = request.get_json() or {}
    input_data = data.get('inputData') or data
    form_type = str(data.get('formType') or input_data.get("project", {}).get("city_form_type") or "calgary").lower()

    try:
        if form_type not in VALID_CITY_FORMS:
            raise ValueError("formType must be calgary or edmonton")
        normalized_input = normalize_calculation_input(input_data)
        result_data = run_calculation(normalized_input)
        if form_type == "edmonton":
            pdf_bytes = build_city_of_edmonton_form_pdf(normalized_input, result_data)
            download_name = "City-of-Edmonton-load-calculation.pdf"
        else:
            pdf_bytes = build_city_of_calgary_form_pdf(normalized_input, result_data)
            download_name = "City-of-Calgary-load-calculation.pdf"
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.exception("City form PDF generation failed")
        return jsonify({"success": False, "message": "City form PDF generation failed."}), 500

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name,
    )

# -------------------------------------------------------
# /send_calculation_email - Sends calculation email with PDF attachment via Mailgun
# -------------------------------------------------------
@api.route('/send_calculation_email', methods=['POST'])
def send_calculation_email():
    """
    Expects JSON:
    {
      "userEmail": "someone@example.com",
      "inputData": { ... },
      "resultData": { ... }
    }
    """
    data = request.get_json() or {}
    user_email = data.get('userEmail')
    input_data = data.get('inputData')

    if not user_email or not EMAIL_RE.match(user_email) or not input_data:
        return jsonify({"success": False, "message": "Missing required data."}), 400

    try:
        normalized_input = normalize_calculation_input(input_data)
        result_data = run_calculation(normalized_input)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    calculation_data = {
        "input": normalized_input,
        "result": result_data
    }

    try:
        pdf_bytes = build_calculation_pdf(calculation_data)
    except Exception as e:
        logger.exception("PDF generation failed")
        return jsonify({"success": False, "message": "PDF generation failed."}), 500

    html_content = build_branded_email()

    MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
    if not MAILGUN_DOMAIN or not MAILGUN_API_KEY:
        return jsonify({"success": False, "message": "Mailgun environment variables not set."}), 500

    mailgun_url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    from_address = f"Real World Electric <mailgun@{MAILGUN_DOMAIN}>"

    try:
        response = requests.post(
            mailgun_url,
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": from_address,
                "to": [user_email],
                "subject": "Your Real World Electric Load Calculation",
                "html": html_content
            },
            files=[("attachment", ("LoadCalculation.pdf", pdf_bytes, "application/pdf"))],
            timeout=12
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.exception("Mailgun calculation email failed")
        return jsonify({"success": False, "message": "Email failed to send."}), 500

    return jsonify({"success": True, "message": "Email sent successfully"}), 200

# -------------------------------------------------------
# /review_form - Renders review request form page
# -------------------------------------------------------
@api.route('/review_form', methods=['GET'])
def review_form():
    return render_template('review_form.html')

# -------------------------------------------------------
# /contact - Renders contact page
# -------------------------------------------------------
@api.route('/contact', methods=['GET'])
def contact():
    return render_template('contact.html')

# -------------------------------------------------------
# /submit_contact - Handles contact form submissions and sends email via Mailgun
# -------------------------------------------------------
@api.route('/submit_contact', methods=['POST'])
def submit_contact():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    
    if not name or not email or not message:
        return "Please fill out all required fields.", 400

    email_body = f"New Contact Form Submission\n\nName: {name}\nEmail: {email}\nMessage: {message}"
    
    MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
    if not MAILGUN_DOMAIN or not MAILGUN_API_KEY:
        return "Mailgun configuration error.", 500

    mailgun_url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    from_address = f"Real World Electric <mailgun@{MAILGUN_DOMAIN}>"
    # Replace with your actual recipient email
    recipient = "Bart@Realworldelectric.com"

    post_data = {
        "from": from_address,
        "to": recipient,
        "subject": "New Contact Form Submission",
        "text": email_body
    }

    try:
        response = requests.post(
            mailgun_url,
            auth=("api", MAILGUN_API_KEY),
            data=post_data,
            timeout=12
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.exception("Contact email failed")
        return "Error sending email.", 500

    # Return "success" so the AJAX script can detect it
    return "success"

# -------------------------------------------------------
# /submit_review_form - Handles expert review requests
# -------------------------------------------------------
@api.route('/submit_review_form', methods=['POST'])
def submit_review_form():
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    phone = request.form.get('phone')
    user_email = request.form.get('email')
    project_address = request.form.get('project_address')
    reason = request.form.get('reason')
    comments = request.form.get('comments')
    calc_input = request.form.get('calcInput')
    calc_result = request.form.get('calcResult')

    if not all([first_name, last_name, phone, user_email, project_address, reason]):
        return "Please fill out all required fields.", 400

    review_content = f"""
    <h2>Load Calculation Review Request</h2>
    <p><strong>Name:</strong> {escape(first_name)} {escape(last_name)}</p>
    <p><strong>Phone:</strong> {escape(phone)}</p>
    <p><strong>Email:</strong> {escape(user_email)}</p>
    <p><strong>Project Address:</strong> {escape(project_address)}</p>
    <p><strong>Reason for Load Calculation:</strong> {escape(reason)}</p>
    <p><strong>Additional Comments:</strong> {escape(comments or '')}</p>
    """
    
    pdf_attachment = None
    if calc_input and calc_result:
        try:
            calc_input_data = json.loads(calc_input)
            calc_result_data = json.loads(calc_result)
            calculation_data = {"input": calc_input_data, "result": calc_result_data}
            pdf_attachment = build_calculation_pdf(calculation_data)
            review_content += "<p>The attached PDF contains the full calculation details.</p>"
        except Exception as e:
            logger.exception("Review calculation PDF generation failed")
            review_content += "<p>Warning: Calculation data could not be processed.</p>"

    MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
    if not MAILGUN_DOMAIN or not MAILGUN_API_KEY:
        return "Mailgun configuration error.", 500

    mailgun_url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    from_address = f"Real World Electric <mailgun@{MAILGUN_DOMAIN}>"
    master_email = "Bart@Realworldelectric.com"

    try:
        files = []
        if pdf_attachment:
            files = [("attachment", ("LoadCalculation.pdf", pdf_attachment, "application/pdf"))]
        response = requests.post(
            mailgun_url,
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": from_address,
                "to": [master_email],
                "subject": "Load Calculation Review Request",
                "html": review_content
            },
            files=files,
            timeout=12
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.exception("Review request email failed")
        return "Failed to send review request.", 500

    confirmation_content = f"""
    <h2>Thank You!</h2>
    <p>Your load calculation review request has been received.</p>
    <p>A Master Electrician will be in touch within 24 hours.</p>
    <p>Thank you for choosing Real World Electric.</p>
    """
    
    try:
        files = []
        if pdf_attachment:
            files = [("attachment", ("LoadCalculation.pdf", pdf_attachment, "application/pdf"))]
        response = requests.post(
            mailgun_url,
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": from_address,
                "to": [user_email],
                "subject": "Your Load Calculation Review Request Has Been Received",
                "html": confirmation_content
            },
            files=files,
            timeout=12
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.exception("Review confirmation email failed")
        return "Failed to send confirmation email.", 500

    return "Thank you! Your review request has been sent. We will contact you shortly."
