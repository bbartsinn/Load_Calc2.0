# routes.py
from flask import Blueprint, request, jsonify, render_template
import requests
import os
import pdfkit  # Used to generate PDF attachments
import json

from services.calculation_engine import (
    calculate_unit_loads,
    combined_load,
    calculate_service_parameters
)
from services.email_template import build_branded_email, build_pdf_content

api = Blueprint('api', __name__)

# -------------------------------------------------------
# /calculate (UNCHANGED)
# -------------------------------------------------------
@api.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No input data provided"}), 400

    try:
        num_units = data.get("num_units", 1)
        conductor_type = data.get("conductor_type", "Copper")
        units = data.get("units", [])

        units_data = []
        for unit in units:
            result = calculate_unit_loads(unit, conductor_type)
            if result:
                units_data.append(result)

        if not units_data:
            return jsonify({"message": "No valid units provided."}), 400

        combined_no_hvac = combined_load(units_data)
        total_hvac_load = sum(u["calculated_load"] - u["calculated_load_no_hvac"] for u in units_data)
        final_combined_load = combined_no_hvac + total_hvac_load

        service_ocp_label, service_conductor_desc = calculate_service_parameters(
            final_combined_load,
            units_data,
            conductor_type
        )

        result = {
            "units": units_data,
            "Combined No-HVAC Load (Watts)": combined_no_hvac,
            "Total HVAC Load (Watts)": total_hvac_load,
            "Total Calculated Load (Watts)": final_combined_load,
            "Total Amps": final_combined_load / 240.0,
            "Service OCP size (Amps)": service_ocp_label,
            "Service Conductor Type and Size": service_conductor_desc
        }

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------
# Updated: /send_calculation_email
# -------------------------------------------------------
@api.route('/send_calculation_email', methods=['POST'])
def send_calculation_email():
    """
    Expects JSON with:
    {
      "userEmail": "someone@example.com",
      "inputData": { ... },
      "resultData": { ... }
    }
    Merges input and result data, generates a PDF from the calculation details,
    builds a branded email, and sends it via Mailgun.
    """
    data = request.get_json() or {}
    user_email = data.get('userEmail')
    input_data = data.get('inputData')
    result_data = data.get('resultData')

    if not user_email or not input_data or not result_data:
        return jsonify({"success": False, "message": "Missing required data."}), 400

    calculation_data = {
        "input": input_data,
        "result": result_data
    }

    pdf_html = build_pdf_content(calculation_data)
    try:
        options = {"enable-local-file-access": ""}
        pdf_bytes = pdfkit.from_string(pdf_html, False, options=options)
    except Exception as e:
        return jsonify({"success": False, "message": f"PDF generation failed: {str(e)}"}), 500

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
            files=[("attachment", ("LoadCalculation.pdf", pdf_bytes, "application/pdf"))]
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": str(e)}), 500

    return jsonify({"success": True, "message": "Email sent successfully"}), 200

# -------------------------------------------------------
# New: /review_form – page for requesting a review & signature
# -------------------------------------------------------
@api.route('/review_form', methods=['GET'])
def review_form():
    return render_template('review_form.html')

# -------------------------------------------------------
# New: /contact – page for customer contact information
# -------------------------------------------------------
@api.route('/contact', methods=['GET'])
def contact():
    return render_template('contact.html')

# -------------------------------------------------------
# Updated: /submit_contact – handles contact form submissions
# -------------------------------------------------------
@api.route('/submit_contact', methods=['POST'])
def submit_contact():
    # Retrieve form data from the landing page contact form
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    
    if not name or not email or not message:
        return "Please fill out all required fields.", 400

    # Compose email content
    email_body = f"New Contact Form Submission\n\nName: {name}\nEmail: {email}\nMessage: {message}"
    
    # Get Mailgun settings from environment variables
    MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
    if not MAILGUN_DOMAIN or not MAILGUN_API_KEY:
        return "Mailgun configuration error.", 500

    mailgun_url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    from_address = f"Real World Electric <mailgun@{MAILGUN_DOMAIN}>"
    # Set this to the email where you want to receive contact form submissions (e.g., your support email)
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
            data=post_data
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Error sending email: {str(e)}", 500

    # Return exactly "success" so that AJAX on the landing page can detect it
    return "success"

# -------------------------------------------------------
# Updated: /submit_review_form – handles expert review requests
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
    <p><strong>Name:</strong> {first_name} {last_name}</p>
    <p><strong>Phone:</strong> {phone}</p>
    <p><strong>Email:</strong> {user_email}</p>
    <p><strong>Project Address:</strong> {project_address}</p>
    <p><strong>Reason for Load Calculation:</strong> {reason}</p>
    <p><strong>Additional Comments:</strong> {comments}</p>
    """
    
    pdf_attachment = None
    if calc_input and calc_result:
        try:
            calc_input_data = json.loads(calc_input)
            calc_result_data = json.loads(calc_result)
            calculation_data = {"input": calc_input_data, "result": calc_result_data}
            pdf_html = build_pdf_content(calculation_data)
            options = {"enable-local-file-access": ""}
            pdf_attachment = pdfkit.from_string(pdf_html, False, options=options)
            review_content += "<p>The attached PDF contains the full calculation details.</p>"
        except Exception as e:
            review_content += f"<p>Warning: Calculation data could not be processed. Error: {str(e)}</p>"

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
            files=files
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Failed to send review request: {str(e)}", 500

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
            files=files
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Failed to send confirmation email: {str(e)}", 500

    return "Thank you! Your review request has been sent. We will contact you shortly."
