# City of Calgary Digital Load Calculator

A Flask app for residential electrical load calculations for single family dwellings, secondary suites, and laneway/backyard suites.

## Run Locally

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:8000
```

## Test

```powershell
python -m unittest discover -s tests -v
```

## Configuration

Optional environment variables:

```text
MAILGUN_DOMAIN=example.com
MAILGUN_API_KEY=...
CORS_ORIGINS=https://your-production-domain.com
```

Mailgun is only required for email/PDF delivery. The calculator itself works without it.

## Notes

- The calculation API validates numeric input and conductor type before calculating.
- Email/PDF generation recomputes the result server-side instead of trusting browser-supplied totals.
- Multi-unit no-HVAC demand uses tiered demand factors so three or more units are not ignored.
- EV charging equipment is counted at 100% of the entered EVSE load.
- A single electric range is counted as 6000 W, plus 40% of the nameplate amount over 12 kW.
- Electric tankless water heaters are counted at 100%.
- Pool/hot tub/spa equipment is counted at 100% of the whole entered nameplate.
- Storage-tank water heaters, dryers, and other fixed loads over 1500 W belong in the additional-load bucket: 25% when an electric range is present, or 100% of the first 6000 W plus 25% of the balance when no electric range is present.
- The on-screen results panel and emailed PDF include calculation breakdown tables showing nameplate load, demand percentage, and included watts.
- Service OCP is calculated for multi-unit scenarios from the final combined service load instead of displaying N/A.
- Conductor sizing uses the 75 degree columns from CEC Table 2 for copper and Table 4 for aluminum.
