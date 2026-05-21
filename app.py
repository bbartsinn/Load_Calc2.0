# app.py

import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template
from flask_cors import CORS
import routes  # Ensure routes.py is in the same directory

app = Flask(__name__)
allowed_origins = os.getenv("CORS_ORIGINS")
if allowed_origins:
    CORS(app, origins=[origin.strip() for origin in allowed_origins.split(",") if origin.strip()])

app.register_blueprint(routes.api, url_prefix='/api')

@app.route('/')
def home():
    # Make sure templates/index.html exists
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
