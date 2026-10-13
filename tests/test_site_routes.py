import unittest

from app import app

GA_ID = "G-K3BF6QGHLL"

HTML_PAGES = [
    "/",
    "/guides/",
    "/guides/calgary-secondary-suite-load-calculation/",
    "/guides/can-100-amp-service-handle-secondary-suite/",
    "/guides/city-of-calgary-load-calculation-form/",
    "/guides/ev-charger-load-calculation-calgary/",
    "/load-calculation-sign-off/",
    "/calculator",
    "/calculator/",
]

STATIC_FILES = [
    "/styles.css",
    "/favicon.svg",
    "/robots.txt",
    "/sitemap.xml",
    "/assets/site.css",
    "/assets/favicon.svg",
    "/assets/rwe-logo.png",
    "/assets/og-image.png",
    "/static/script.js",
    "/static/style.css",
    "/api/review_form",
    "/api/contact",
]


class SiteRoutesTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _text(self, path):
        with self.client.get(path) as response:
            return response.get_data(as_text=True)

    def test_html_pages_return_200_with_single_ga_tag(self):
        for path in HTML_PAGES:
            with self.subTest(path=path):
                with self.client.get(path) as response:
                    self.assertEqual(response.status_code, 200)
                    body = response.get_data(as_text=True)
                self.assertEqual(body.count(f"gtag/js?id={GA_ID}"), 1)
                self.assertNotIn("loadcalculation.realworldelectric.com", body)
                self.assertNotIn("smartplanning.realworldelectric.com", body)

    def test_static_files_return_200(self):
        for path in STATIC_FILES:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()

    def test_calculator_page_canonical_and_absolute_assets(self):
        body = self._text("/calculator")
        self.assertIn('<link rel="canonical" href="https://realworldelectric.com/calculator">', body)
        self.assertIn('href="/static/style.css', body)
        self.assertIn('src="/static/script.js', body)

    def test_landing_links_to_calculator(self):
        body = self._text("/")
        self.assertIn('href="/calculator"', body)
        self.assertIn("<title>", body)

    def test_sitemap_includes_calculator(self):
        body = self._text("/sitemap.xml")
        self.assertIn("<loc>https://realworldelectric.com/calculator</loc>", body)

    def test_trailing_slash_redirects(self):
        for path, target in [
            ("/guides", "/guides/"),
            ("/guides/ev-charger-load-calculation-calgary", "/guides/ev-charger-load-calculation-calgary/"),
            ("/load-calculation-sign-off", "/load-calculation-sign-off/"),
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 301)
                self.assertTrue(response.headers["Location"].endswith(target))

    def test_unknown_paths_404(self):
        for path in ["/guides/does-not-exist/", "/guides/does-not-exist", "/nope", "/assets/nope.png"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


class LegacyHostRedirectTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _get(self, host, path):
        return self.client.get(path, base_url=f"https://{host}")

    def test_loadcalculation_root_goes_to_calculator(self):
        response = self._get("loadcalculation.realworldelectric.com", "/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], "https://realworldelectric.com/calculator")

    def test_loadcalculation_keeps_api_paths_and_query(self):
        response = self._get("loadcalculation.realworldelectric.com", "/api/review_form?x=1")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], "https://realworldelectric.com/api/review_form?x=1")

    def test_loadcalculation_post_is_not_redirected(self):
        response = self.client.post(
            "/api/calculate",
            base_url="https://loadcalculation.realworldelectric.com",
            json={"conductor_type": "Copper", "units": [{"area_m2": 100}]},
        )
        self.assertEqual(response.status_code, 200)

    def test_smartplanning_keeps_paths(self):
        response = self._get("smartplanning.realworldelectric.com", "/guides/ev-charger-load-calculation-calgary/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.headers["Location"],
            "https://realworldelectric.com/guides/ev-charger-load-calculation-calgary/",
        )

    def test_www_goes_to_apex(self):
        response = self._get("www.realworldelectric.com", "/calculator")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], "https://realworldelectric.com/calculator")

    def test_canonical_and_render_hosts_not_redirected(self):
        for host in ["realworldelectric.com", "load-calc2-0.onrender.com", "localhost"]:
            with self.subTest(host=host):
                self.assertEqual(self._get(host, "/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
