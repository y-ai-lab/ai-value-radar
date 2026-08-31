import unittest

from scripts.secret_scan import contains_secret_pattern


class SecretScanTests(unittest.TestCase):
    def test_url_slug_is_not_a_secret(self):
        content = "https://example.com/articles/musk-says-groks-political-lean-is-a-function-of-sf-bay-area"
        self.assertFalse(contains_secret_pattern(content))

    def test_key_like_text_is_detected(self):
        content = "api_key=sk-ABC1234567890_DEFghijklmnopQRSTUV"
        self.assertTrue(contains_secret_pattern(content))

    def test_key_like_query_parameter_is_detected(self):
        content = "https://example.com/callback?key=sk-ABC1234567890_DEFghijklmnopQRSTUV"
        self.assertTrue(contains_secret_pattern(content))


if __name__ == "__main__":
    unittest.main()
