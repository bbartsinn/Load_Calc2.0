# Cutover: serve everything from the Flask service on realworldelectric.com

After this branch is merged and deployed, one Render web service
(`Load_Calc2.0`, `srv-cup5f52j1k6c739g43ag`, `load-calc2-0.onrender.com`) serves:

| URL | What |
| --- | --- |
| `/` | Smart Planning landing page (`site/index.html`) |
| `/guides/`, `/guides/<slug>/` | Guides (`site/guides/...`) |
| `/load-calculation-sign-off/` | Sign-off page |
| `/calculator` (and `/calculator/`) | Load calculator (`templates/index.html`) |
| `/api/*`, `/static/*` | Calculator API and assets (unchanged) |
| `/styles.css`, `/favicon.svg`, `/assets/*`, `/robots.txt`, `/sitemap.xml` | Landing assets |

`app.py` → `redirect_legacy_hosts()` 301-redirects GET/HEAD requests on legacy hostnames:

- `loadcalculation.realworldelectric.com/` → `https://realworldelectric.com/calculator`
- `loadcalculation.realworldelectric.com/<path>` → `https://realworldelectric.com/<path>` (e.g. old `/api/review_form` email links)
- `smartplanning.realworldelectric.com/<path>` → `https://realworldelectric.com/<path>`
- `www.realworldelectric.com/<path>` → `https://realworldelectric.com/<path>`

POSTs on legacy hosts are served, not redirected (a 301 would turn them into GETs).
`localhost` and `*.onrender.com` are never redirected. Override the target with the
`CANONICAL_HOST` env var if ever needed (default `realworldelectric.com`).

DNS today (checked 2026-10-06): apex `A 216.24.57.1` (Render), `www` and `smartplanning`
CNAME `loadcalclandingpage.onrender.com` (static site), `loadcalculation` CNAME
`load-calc2-0.onrender.com` (Flask). All Render targets, so **no DNS record changes are
strictly required**: Render routes by the custom domain attached to each service.

## Steps

1. **Merge the PR** into `main`. Render auto-deploys the Flask service (or Manual Deploy).
2. **Verify on the onrender URL before touching domains** (not redirected there):
   `https://load-calc2-0.onrender.com/`, `/guides/`, `/load-calculation-sign-off/`,
   `/calculator`, run a calculation, download a City form PDF, `/sitemap.xml`.
3. **Static site (the one at `loadcalclandingpage.onrender.com`) → Settings → Custom Domains:** delete
   `realworldelectric.com`, `www.realworldelectric.com` and `smartplanning.realworldelectric.com`.
   (Render only lets a domain live on one service, so this must happen first. Brief
   downtime on those hostnames starts here; do steps 3–4 back to back.)
4. **Flask service (`Load_Calc2.0`) → Settings → Custom Domains:** add
   `realworldelectric.com` (Render adds `www` alongside it; if not, add
   `www.realworldelectric.com`) and `smartplanning.realworldelectric.com`.
   `loadcalculation.realworldelectric.com` is already attached; keep it.
   Click **Verify** on each; wait for certificates to show *Issued* (usually minutes).
5. **DNS (GoDaddy):** only change if Render's verify asks for it. Recommended end state:
   - `@` A `216.24.57.1` (already set)
   - `www` CNAME `load-calc2-0.onrender.com` (currently points at the static site; CNAME to
     the static host keeps working only while Render maps the domain, so switch it for clarity)
   - `smartplanning` CNAME `load-calc2-0.onrender.com`
   - `loadcalculation` CNAME `load-calc2-0.onrender.com` (already set)
6. **Env vars:** if `CORS_ORIGINS` is set on the service, add `https://realworldelectric.com`.
   Check Mailgun/any webhook settings that reference `loadcalculation.*` (the app code now
   emails `https://realworldelectric.com/api/...` links).
7. **Smoke test live:**
   ```
   curl -sI https://realworldelectric.com/ | head -1                      # 200
   curl -sI https://realworldelectric.com/calculator | head -1            # 200
   curl -sI https://www.realworldelectric.com/guides/ | grep -i location  # https://realworldelectric.com/guides/
   curl -sI https://smartplanning.realworldelectric.com/ | grep -i location   # https://realworldelectric.com/
   curl -sI https://loadcalculation.realworldelectric.com/ | grep -i location # https://realworldelectric.com/calculator
   ```
8. **Search Console:** submit `https://realworldelectric.com/sitemap.xml`; use the
   Change of Address tool / URL Inspection for the old subdomains if they are verified.
   Update the Google Business Profile website link if it points at a subdomain.
9. **Retire the static site** (the one at `loadcalclandingpage.onrender.com`) once everything checks out for a few
   days — suspend first, delete later. Its repo (`LoadCalculationLanding`) is now copied
   into `site/` here; edit landing pages in this repo from now on.
