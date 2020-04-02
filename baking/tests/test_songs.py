# Generic
import unittest

# Libs
from flask_testing import TestCase

# Own
from baking.manage import app


class TestSongs(TestCase):
    def create_app(self):
        app.config.from_object('config.testing')
        return app


class TestSongEndPoints(TestSongs):
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
