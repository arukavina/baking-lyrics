# Generic
import unittest

# Libs
from flask_testing import TestCase
from flask import current_app as app


class TestViews(TestCase):
    def create_app(self):
        app.config.from_object('config.development')
        return app

    def setUp(self):
        self.app = self.create_app()
        self.app.testing = True  # To handle error properly by test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_ping_get(self):
        response = self.client.get("/api/v1/general/ping")
        print("\n\nResponse (test_ping_get): " + str(response.json))
        self.assertEqual(str(response.json), "pong!")

    def test_ping_post(self):
        response = self.client.post("/api/v1/general/ping")
        print("\n\nResponse (test_ping_post): " + str(response.json))
        self.assertEqual(str(response.json), "pong!")

    def test_random(self):
        response = self.client.get("/api/v1/general/random")
        art = response.json["artist"][0]
        print("\n\nResponse (test_random): " + art["name"])
        self.assertIsNotNone(response)


if __name__ == '__main__':
    unittest.main()
