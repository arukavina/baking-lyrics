import unittest
from flask_testing import TestCase

from baking.main import create_app


class TestViews(TestCase):
    def create_app(self):

        app = create_app('config/testing.py')
        app.app_context().push()

        return app

    def setUp(self):
        self.app = self.create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_ping_get(self):
        response = self.client.get("/api/v1/general/ping")
        print("\n\nResponse: " + str(response.json))
        self.assertEqual(response.json, "pong!")

    def test_ping_post(self):
        response = self.client.post("/api/v1/general/ping")
        print("\n\nResponse: " + str(response.json))
        self.assertEqual(response.json, "pong!")

    def test_random(self):
        response = self.client.get("/api/v1/general/random")
        art = response.json["artist"][0]
        print("\n\nResponse: " + art["name"])
        self.assertIsNotNone(response)


if __name__ == '__main__':
    unittest.main()
