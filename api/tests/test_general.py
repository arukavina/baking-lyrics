import unittest

from flask import Blueprint
from flask_testing import TestCase

from api.v1 import create_app, api, limiter
# from api.v1.endpoints.artists import ns as bands_namespace
# from api.v1.endpoints.genres import ns as genres_namespace
# from api.v1.endpoints.songs import ns as songs_namespace
# from api.v1.endpoints.artificial_titles import ns as artificial_titles_namespace
# from api.v1.endpoints.artificial_songs import ns as artificial_songs_namespace
from api.v1.endpoints.general import ns as general_namespace


class TestViews(TestCase):
    def create_app(self):

        app = create_app('../config/development.py')

        app.app_context().push()

        limiter.init_app(app)

        blueprint = Blueprint('api', __name__, url_prefix='/api/v1')
        api.init_app(blueprint)

        # api.add_namespace(bands_namespace)
        # api.add_namespace(genres_namespace)
        # api.add_namespace(songs_namespace)
        # api.add_namespace(artificial_titles_namespace)
        # api.add_namespace(artificial_songs_namespace)
        api.add_namespace(general_namespace)

        app.register_blueprint(blueprint)

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


if __name__ == '__main__':
    unittest.main()
