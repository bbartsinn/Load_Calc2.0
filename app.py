# app.py

import os
from dotenv import load_dotenv

# 1) Load environment variables from .env file
load_dotenv()

# Optional debug: print the loaded environment variables
print("MAILGUN_DOMAIN:", os.getenv('MAILGUN_DOMAIN'))
print("MAILGUN_API_KEY:", os.getenv('MAILGUN_API_KEY'))

from flask import Flask, render_template
from flask_cors import CORS
import routes  # Ensure routes.py is in the same directory

app = Flask(__name__)
CORS(app)

# 2) Register the Blueprint
app.register_blueprint(routes.api, url_prefix='/api')

@app.route('/')
def home():
    # Make sure templates/index.html exists
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
