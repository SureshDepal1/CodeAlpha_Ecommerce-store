from django.test import TestCase, override_settings
from django.urls import reverse


class LegalPageTests(TestCase):
    def test_pages_load_and_footer_links_are_present(self):
        for name in ("privacy", "terms", "contact"):
            response = self.client.get(reverse(f"store:{name}"))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "TODO")
            self.assertNotContains(response, "Lorem")
            self.assertNotContains(response, "[")

        home = self.client.get(reverse("store:home"))
        for name in ("privacy", "terms", "contact"):
            self.assertContains(home, reverse(f"store:{name}"))

    @override_settings(
        RETURN_POLICY_SUMMARY="Returns are handled by the store after contact.",
        DELIVERY_TIME_SUMMARY="Delivery information is provided by the store.",
        LEGAL_JURISDICTION="The configured jurisdiction.",
    )
    def test_optional_terms_sections_are_shown_when_configured(self):
        response = self.client.get(reverse("store:terms"))
        self.assertContains(response, "Returns are handled")
        self.assertContains(response, "Delivery information")
        self.assertContains(response, "configured jurisdiction")

    def test_contact_page_is_neutral_when_details_are_empty(self):
        response = self.client.get(reverse("store:contact"))
        self.assertContains(response, "Contact details have not been configured yet.")

    def test_external_resource_disclosure_matches_local_templates(self):
        response = self.client.get(reverse("store:privacy"))
        self.assertContains(response, "local CSS and JavaScript files")
        self.assertContains(response, "third-party web resources")