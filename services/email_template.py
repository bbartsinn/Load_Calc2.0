def build_branded_email():
    """
    Returns the HTML content for the branded email sent to the user.
    This email thanks the user for using Real World Electric Digital Tools for their project,
    informs them that their load calculation is attached as a PDF, and provides clear
    action buttons for getting an expert review and for contacting us.
    """
    # Branding colors
    brand_color = "#FFD800"       # Yellow
    text_color = "#000000"        # Black
    background_color = "#ffffff"  # White

    # Contact information (update URLs/links as needed)
    contact_info = (
        '<p style="font-size: 12px; color: #555;">'
        'Contact Us: Phone: 403-808-2811 | Whatsapp: 403-808-2811 | '
        'Telegram: <a href="https://t.me/rwemec" style="color:#000;">@t.me/rwemec</a> | '
        '<a href="https://facebook.com/RWEINC" style="color:#000;">Facebook</a> | '
        'Email: <a href="mailto:Bart@Realworldelectric.com" style="color:#000;">Bart@Realworldelectric.com</a>'
        '</p>'
    )

    # Action button for expert review – styled responsively
    review_button = (
        '<p style="text-align: center; margin: 20px 0;">'
        '<a href="https://yourdomain.com/review_form" '
        'style="display:block; max-width:300px; width:90%; margin:0 auto; '
        'background:' + text_color + '; color:' + brand_color + '; padding: 12px 0; '
        'text-align:center; text-decoration:none; border-radius:5px; font-weight:bold; font-size:16px;">'
        'Get Expert Review'
        '</a>'
        '</p>'
    )

    # Action button for contacting us – styled similarly
    contact_button = (
        '<p style="text-align: center; margin: 20px 0;">'
        '<a href="https://yourdomain.com/contact" '
        'style="display:block; max-width:300px; width:90%; margin:0 auto; '
        'background:' + text_color + '; color:' + brand_color + '; padding: 12px 0; '
        'text-align:center; text-decoration:none; border-radius:5px; font-weight:bold; font-size:16px;">'
        'Contact Us'
        '</a>'
        '</p>'
    )

    html = f"""
    <html>
      <head>
        <meta charset="UTF-8">
        <title>Thank You from Real World Electric</title>
      </head>
      <body style="margin: 0; padding: 20px; font-family: Arial, sans-serif; background: {background_color}; color: {text_color};">
        <div style="background: {brand_color}; padding: 20px; text-align: center;">
          <h1 style="margin: 0;">Real World Electric Digital Tools</h1>
        </div>
        <div style="padding: 20px;">
          <h2>Thank You for Using Our Digital Tools!</h2>
          <p>We appreciate you choosing Real World Electric for your project.</p>
          <p>Your detailed load calculation is attached as a PDF for your records.</p>
          <p>If you would like your load calculation reviewed and signed by a master electrician, please click the button below.</p>
          {review_button}
          <p>If you need any assistance, please use the contact button below.</p>
          {contact_button}
          <p style="margin-top: 30px; font-size: 14px;">
            Thank you,<br>
            The Real World Electric Team
          </p>
          {contact_info}
        </div>
      </body>
    </html>
    """
    return html


def build_pdf_content(calculation_data):
    """
    Returns HTML content for the PDF attachment containing the load calculation details.
    
    The PDF includes:
      - A header with your RWE logo in the top left.
      - Separate tables for each unit's input data and calculation results.
      - A table for overall totals.
      - A footer with Real World Electric's contact information.
    
    Expected structure for calculation_data:
    {
       "input": {
           "conductor_type": "Copper",
           "units": [
              {
                 "unit_type": "SFD",
                 "area_m2": ...,
                 "space_heating": ...,
                 ...
              },
              ...
           ]
       },
       "result": {
           "units": [
              {
                 "unit_type": "SFD",
                 "calculated_load": ...,
                 "calculated_load_no_hvac": ...,
                 ...
              },
              ...
           ],
           "Combined No-HVAC Load (Watts)": ...,
           "Total HVAC Load (Watts)": ...,
           "Total Calculated Load (Watts)": ...,
           "Total Amps": ...,
           "Service OCP size (Amps)": ...,
           "Service Conductor Type and Size": ...
       }
    }
    """
    html = """<html>
      <head>
        <meta charset="UTF-8">
        <title>Load Calculation Details</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            padding: 20px;
            position: relative;
            margin: 0;
          }
          header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
          }
          header img {
            max-width: 150px;
            height: auto;
          }
          header h1 {
            flex: 1;
            text-align: center;
            margin: 0;
          }
          h2, h3 {
            text-align: center;
          }
          table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
          }
          th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
          }
          th {
            background-color: #f2f2f2;
          }
          footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            font-size: 12px;
            color: #555;
            text-align: center;
            padding: 10px 20px;
            border-top: 1px solid #ddd;
          }
        </style>
      </head>
      <body>
        <header>
          <!-- Logo in the top left -->
          <img src="file:///C:/Users/User/Copies/ELC_Email/Images/logo.png" alt="RWE Logo">
          <h1>Load Calculation Details</h1>
        </header>
        <h2>Input Data</h2>
    """

    # --- Input Data Section ---
    input_data = calculation_data.get("input", {})
    conductor_type = input_data.get("conductor_type", "N/A")
    html += f"<p style='text-align: center;'><strong>Conductor Type:</strong> {conductor_type}</p>"
    
    units_input = input_data.get("units", [])
    if units_input:
        for unit in units_input:
            unit_type = unit.get("unit_type", "Unit")
            html += f"<h3>Input Data - {unit_type}</h3>"
            html += "<table><tbody>"
            for key, value in unit.items():
                html += f"<tr><th>{key}</th><td>{value}</td></tr>"
            html += "</tbody></table>"
    else:
        html += "<p style='text-align: center;'>No unit input data available.</p>"

    # --- Calculation Results Section ---
    html += "<h2>Calculation Results</h2>"
    
    result_data = calculation_data.get("result", {})
    units_result = result_data.get("units", [])
    if units_result:
        for unit in units_result:
            unit_type = unit.get("unit_type", "Unit")
            html += f"<h3>Results - {unit_type}</h3>"
            html += "<table><tbody>"
            for key, value in unit.items():
                html += f"<tr><th>{key}</th><td>{value}</td></tr>"
            html += "</tbody></table>"
    else:
        html += "<p style='text-align: center;'>No unit calculation results available.</p>"

    # --- Overall Totals Section ---
    overall_keys = ["Combined No-HVAC Load (Watts)", "Total HVAC Load (Watts)", 
                    "Total Calculated Load (Watts)", "Total Amps", 
                    "Service OCP size (Amps)", "Service Conductor Type and Size"]
    html += "<h2>Overall Totals</h2>"
    html += "<table><tbody>"
    for key in overall_keys:
        if key in result_data:
            html += f"<tr><th>{key}</th><td>{result_data[key]}</td></tr>"
    html += "</tbody></table>"

    # --- Footer Section with Contact Info ---
    html += """
        <footer>
          Real World Electric | Phone: 403-808-2811 | Whatsapp: 403-808-2811 | 
          Telegram: <a href="https://t.me/rwemec" style="color:#555;">@rwemec</a> | 
          <a href="https://facebook.com/RWEINC" style="color:#555;">Facebook</a> | 
          Email: <a href="mailto:Bart@Realworldelectric.com" style="color:#555;">Bart@Realworldelectric.com</a>
        </footer>
    """

    html += """
      </body>
    </html>
    """
    return html
