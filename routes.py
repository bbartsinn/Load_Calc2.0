# routes.py
from flask import Blueprint, request, jsonify, render_template
import requests
import os
import pdfkit  # NEW: used to generate PDF attachments

from services.calculation_engine import (
    calculate_unit_loads,
    combined_load,
    calculate_service_parameters
)
# Updated email template imports – we now have two new helper functions:
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
    We now:
      • Merge the input and result data into one dictionary.
      • Generate a PDF from these details (using pdfkit) with local file access enabled.
      • Build a branded email (with your Real World Electric colors, thank-you text, and an action button)
      • Send the email via Mailgun with the PDF attached.
    """
    data = request.get_json() or {}
    user_email = data.get('userEmail')
    input_data = data.get('inputData')
    result_data = data.get('resultData')

    if not user_email or not input_data or not result_data:
        return jsonify({"success": False, "message": "Missing required data."}), 400

    # Combine the calculation data
    calculation_data = {
        "input": input_data,
        "result": result_data
    }

    # Generate the PDF attachment from calculation data with local file access enabled
    pdf_html = build_pdf_content(calculation_data)
    try:
        options = {"enable-local-file-access": ""}
        pdf_bytes = pdfkit.from_string(pdf_html, False, options=options)
    except Exception as e:
        return jsonify({"success": False, "message": f"PDF generation failed: {str(e)}"}), 500

    # Build the branded email content
    html_content = build_branded_email()

    MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
    if not MAILGUN_DOMAIN or not MAILGUN_API_KEY:
        return jsonify({
            "success": False,
            "message": "Mailgun environment variables not set."
        }), 500

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
# New: /review_form – page for the customer to request a review & signature
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
# New: /submit_contact – handles contact form submissions
# -------------------------------------------------------
@api.route('/submit_contact', methods=['POST'])
def submit_contact():
    # Retrieve form data from the contact page
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    
    # For now, you can simply return a confirmation message.
    # In production, you might want to send an email or store the message.
    return f"Thank you {name}, we have received your message and will contact you shortly."

# -------------------------------------------------------
# Updated: /submit_review_form – handles expert review requests
# -------------------------------------------------------
import json

@api.route('/submit_review_form', methods=['POST'])
def submit_review_form():
    """
    Handles the submission of the expert review request form.
    Expects the following form fields:
      - first_name, last_name, phone, email (user's email), project_address, reason, comments
      - Hidden fields: calcInput, calcResult (JSON strings of calculation data)
    Upon submission, the system will:
      1. Email the review request (with the attached calculation PDF) to Bart@Realworldelectric.com.
      2. Email the user a confirmation message (with the attached PDF) indicating that their review request has been received.
    """
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    phone = request.form.get('phone')
    user_email = request.form.get('email')  # User's email for confirmation
    project_address = request.form.get('project_address')
    reason = request.form.get('reason')
    comments = request.form.get('comments')
    calc_input = request.form.get('calcInput')  # Hidden field with calculation input data (JSON string)
    calc_result = request.form.get('calcResult')  # Hidden field with calculation result data (JSON string)

    # Ensure all required fields are provided
    if not all([first_name, last_name, phone, user_email, project_address, reason]):
        return "Please fill out all required fields.", 400

    # Build the email content for you (the master electrician)
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
    # If calculation data is available, try to parse it and generate a PDF
    if calc_input and calc_result:
        try:
            calc_input_data = json.loads(calc_input)
            calc_result_data = json.loads(calc_result)
            calculation_data = {"input": calc_input_data, "result": calc_result_data}
            pdf_html = build_pdf_content(calculation_data)
            options = {"enable-local-file-access": ""}
            pdf_attachment = pdfkit.from_string(pdf_html, False, options=options)
            # Include a note in the email that the PDF is attached
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

    # Send email to you with the review request and attached PDF if available
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

    # Build the confirmation email content for the user
    confirmation_content = f"""
    <h2>Thank You!</h2>
    <p>Your load calculation review request has been received.</p>
    <p>A Master Electrician will be in touch within 24 hours.</p>
    <p>Thank you for choosing Real World Electric.</p>
    """
    
    # Send confirmation email to the user (with PDF attached if available)
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

