import unittest
from flask_testing import TestCase

from baking.main import create_app

class TestViews(TestCase):
    def create_app(self):

        app = create_app('config/development.py')
        app.app_context().push()

        return app

    def setUp(self):
        self.app = self.create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_song_get(self):

        from baking.main.database.models import Song
        from baking.main.v1.endpoints.songs import song
        from flask_restplus import marshal

        id_testing = 1
        g = marshal(Song.query.filter(Song.id == id_testing).one(), song)

        response = self.client.get("/api/v1/songs/{}".format(id_testing))
        print("\n\nResponse: " + str(response.json))
        self.assertEqual(response.json, g)


if __name__ == '__main__':
    unittest.main()
