# app.py
#
# One Flask app serves everything on https://realworldelectric.com:
#   /                          Smart Planning landing page   (site/index.html)
#   /guides/, /guides/<slug>/  guides                         (site/guides/...)
#   /load-calculation-sign-off/                               (site/load-calculation-sign-off/)
#   /calculator                load calculator                (templates/index.html)
#   /api/*                     calculator API                 (routes.py blueprint, unchanged)
#   /static/*                  calculator JS/CSS              (unchanged)
#
# Legacy hostnames (loadcalculation.*, smartplanning.*, www.*) are 301-redirected
# to the canonical host by redirect_legacy_hosts() below, so after the DNS/Render
# cutover all hostnames can point at this one service.

import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, send_from_directory, redirect, request, abort
from flask_cors import CORS
import routes  # Ensure routes.py is in the same directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(BASE_DIR, "site")

CANONICAL_HOST = os.getenv("CANONICAL_HOST", "realworldelectric.com").strip().lower()
CANONICAL_ORIGIN = f"https://{CANONICAL_HOST}"

# Old hostname -> function(path) returning the new path on the canonical host.
LEGACY_HOSTS = {
    # Old calculator host: its "/" was the calculator; /api/* and /static/* keep their paths.
    "loadcalculation.realworldelectric.com": lambda path: "/calculator" if path in ("", "/") else path,
    # Old landing host: paths are identical on the new site.
    "smartplanning.realworldelectric.com": lambda path: path or "/",
    # www -> apex.
    "www.realworldelectric.com": lambda path: path or "/",
}

app = Flask(__name__)
allowed_origins = os.getenv("CORS_ORIGINS")
if allowed_origins:
    CORS(app, origins=[origin.strip() for origin in allowed_origins.split(",") if origin.strip()])

app.register_blueprint(routes.api, url_prefix='/api')


@app.before_request
def redirect_legacy_hosts():
    """301 legacy hostnames to the canonical URL.

    Only GET/HEAD are redirected. A 301 on a POST would be replayed as a GET by
    browsers, so form/API POSTs that still hit an old hostname (e.g. a cached
    copy of the old calculator page) are served normally instead of broken.
    Hosts not listed (localhost, *.onrender.com, the canonical host) are untouched.
    """
    host = (request.host or "").split(":")[0].lower()
    mapper = LEGACY_HOSTS.get(host)
    if mapper is None or request.method not in ("GET", "HEAD"):
        return None
    target = CANONICAL_ORIGIN + mapper(request.path)
    query = request.query_string.decode("utf-8", "ignore")
    if query:
        target += "?" + query
    return redirect(target, code=301)


def _site_page(*parts):
    """Serve site/<parts>/index.html, or 404 if it does not exist."""
    rel = os.path.join(*parts, "index.html") if parts else "index.html"
    if not os.path.isfile(os.path.join(SITE_DIR, rel)):
        abort(404)
    return send_from_directory(SITE_DIR, rel)


# ---- Landing site -----------------------------------------------------------

@app.route('/')
def home():
    return _site_page()


@app.route('/guides')
def guides_no_slash():
    return redirect('/guides/', code=301)


@app.route('/guides/')
def guides_index():
    return _site_page("guides")


@app.route('/guides/<slug>')
def guide_no_slash(slug):
    if not os.path.isfile(os.path.join(SITE_DIR, "guides", slug, "index.html")):
        abort(404)
    return redirect(f'/guides/{slug}/', code=301)


@app.route('/guides/<slug>/')
def guide(slug):
    return _site_page("guides", slug)


@app.route('/load-calculation-sign-off')
def sign_off_no_slash():
    return redirect('/load-calculation-sign-off/', code=301)


@app.route('/load-calculation-sign-off/')
def sign_off():
    return _site_page("load-calculation-sign-off")


@app.route('/<any("styles.css", "favicon.svg", "robots.txt", "sitemap.xml", "og-image-generator.html"):filename>')
def site_root_file(filename):
    return send_from_directory(SITE_DIR, filename)


@app.route('/assets/<path:filename>')
def site_assets(filename):
    return send_from_directory(os.path.join(SITE_DIR, "assets"), filename)


# ---- Calculator -------------------------------------------------------------

@app.route('/calculator')
@app.route('/calculator/')
def calculator():
    return render_template('index.html')


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
