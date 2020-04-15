# Generic
import unittest

# Libs
from flask_testing import TestCase

# Own
#from baking.manage import app
from flask import current_app as app


class TestGeneral(TestCase):

    def create_app(self):
        app.config.from_object('config.default')
        app.config.from_object('config.testing')
        return app


class TestEndPoints(TestGeneral):

    def test_random(self):
        print('test_random')
        response = self.client.get("/api/v1/general/random")
        art = response.json["artist"][0]
        print("Response (test_random): " + art["name"])
        self.assertIsNotNone(response)

    def test_ping_get(self):
        print('test_ping_get')
        response = self.client.get("/api/v1/general/ping")
        print("Response (test_ping_get): " + str(response.json))
        self.assertEqual(str(response.json), "pong!")

    def test_ping_post(self):
        print('test_ping_post')
        client = self.client
        response = client.post("/api/v1/general/ping")
        print("Response (test_ping_post): " + str(response.json))
        self.assertEqual(str(response.json), "pong!")


if __name__ == '__main__':
    unittest.main()
