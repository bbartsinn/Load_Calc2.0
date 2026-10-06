# Real World Electric — Smart Planning Tools (Landing Page)

Landing page for https://realworldelectric.com/ — the hub for Real World Electric's free tools for electricians and service experts, starting with the Calgary & Edmonton Electrical Load Calculator.

## Why the site wasn't ranking (July 2026 audit)

The single biggest problem: **the page was not indexed by Google at all.** It appeared for zero queries, including a search for its own exact URL. No amount of on-page SEO matters until Google indexes the page. Contributing causes, in order of impact:

1. **Never verified in Google Search Console / never submitted the sitemap.** New subdomains with no inbound links can sit unindexed indefinitely — Google simply never discovers them.
2. **Zero backlinks.** Nothing anywhere on the web linked to `smartplanning.realworldelectric.com`. Even the calculator app (which *is* indexed) didn't link back to it.
3. **Authority split across three separate subdomains.** Google treats `realworldelectric.com` (empty), `smartplanning.*` (landing) and `loadcalculation.*` (app) as three unrelated sites. Competitors (24/7 Electric, Flux Renewables, Hauer Power) host their calculators on established domains with service pages, reviews and years of links.
4. **Visible keyword-stuffing block** ("Built for searches like yours" grid of raw search queries) — a classic low-quality signal.
5. **FAQ structured data didn't match the visible FAQ** — different questions in the JSON-LD than on the page.
6. **Weak social preview** — `og:image` pointed at a square logo instead of a 1200×630 card, so shared links looked broken/bland.

## What was changed in the redesign

On-page: single-file page with inlined critical CSS (fast LCP), mobile-first layout with hamburger nav and sticky mobile CTA, cleaned title/description, removed meta keywords and the visible keyword grid, `Electrician` + `WebSite` + `SoftwareApplication` + `FAQPage` structured data where the FAQ schema exactly matches the visible FAQ, proper OG/Twitter card tags with a real 1200×630 image, SVG favicon, tools-hub section positioning the site as a growing toolbox for Alberta electricians.

## Launch checklist (do these — they matter more than the page itself)

- [ ] **Generate the social image:** open `og-image-generator.html` in a browser, click Download, commit the file as `assets/og-image.png`. The page already references it.
- [ ] **Google Search Console:** verify `smartplanning.realworldelectric.com` (DNS or HTML-file method), submit `sitemap.xml`, then use **URL Inspection → Request Indexing** on the homepage. This alone typically gets the page indexed within days.
- [ ] **Bing Webmaster Tools:** same thing (imports from GSC in one click).
- [ ] **Link the calculator app back here:** add a visible link on `loadcalculation.realworldelectric.com` (header or footer) to `https://realworldelectric.com/` — it's already indexed, so it passes discovery + relevance. Also add a proper `<title>`, meta description and canonical to the app while you're in there.
- [ ] **Google Business Profile:** add the smartplanning URL as the website (or a link) on the Real World Electric GBP listing — the strongest local signal available for "Calgary" queries.
- [ ] **Update directory listings** (YellowPages, Facebook page, etc.) to link to the tool.
- [ ] **Earn 3–5 real local links:** Calgary/Edmonton home-builder forums, Reddit (r/Calgary, r/alberta, r/electricians when relevant), secondary-suite Facebook groups, ENMAX/EPCOR adjacent blogs, BILD Calgary members. One genuinely useful "free tool that fills the City form for you" post outperforms any on-page tweak.
- [ ] **After sharing on social:** run the URL through Facebook Sharing Debugger and LinkedIn Post Inspector once to refresh their cache of the new og-image.
- [ ] **Longer term:** consider consolidating tools onto one domain (e.g. `realworldelectric.com/tools/...`) so every link builds one site's authority instead of three.

## Files

- `index.html` — the landing page (all CSS inlined; `styles.css` no longer used)
- `assets/favicon.svg` — favicon
- `assets/og-image.png` — social preview card (generate via `og-image-generator.html`)
- `og-image-generator.html` — one-click generator for the social card (not linked from the site)
- `sitemap.xml`, `robots.txt`
