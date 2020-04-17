# Generic
import unittest

# Libs
from flask_testing import TestCase

# Own
from baking.manage import app
#from flask import current_app as app


class TestSongs(TestCase):
    def create_app(self):
        app.config.from_object('config.testing')
        return app


class TestSongEndPoints(TestSongs):
    def test_song_create(self):
        import json

        headers = {'content-type': 'application/json'}
        data = {"title": "gloria",
                "lyrics": "gloria patri et filio et spiritui sancto, sicut erat in principio et nunc et semper et in saecula saeculorum amen",
                "pub_date": "1987-12-05T00:00:00", "artist_id": 1, "country": "US"}

        response = self.client.post('api/v1/songs/', data=json.dumps(data), headers=headers)
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 201)

    def test_song_get(self):
        from baking.main.database.models import Song
        from baking.main.v1.endpoints.songs import song
        from flask_restplus import marshal

        id_testing = 1
        g = marshal(Song.query.filter(Song.id == id_testing).one(), song)

        response = self.client.get('/api/v1/songs/{}'.format(id_testing))
        print('\n\nResponse: ' + str(response.json))
        self.assertEqual(response.json, g)

    def test_song_update(self):
        from baking.main.database.models import Song
        from baking.main import db

        import json

        data = {"artist_id": 1, "title": "Amen", "lyrics": "I heard from a friend of a friend"}
        headers = {'content-type': 'application/json'}
        id_testing = db.session.query(db.func.max(Song.id)).scalar()
        response = self.client.put('api/v1/songs/{}'.format(id_testing), data=json.dumps(data), headers=headers)
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 204)

    def test_song_delete(self):
        from baking.main.database.models import Song
        from baking.main import db

        id_testing = db.session.query(db.func.max(Song.id)).scalar()
        response = self.client.delete('api/v1/songs/{}'.format(id_testing))
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 204)


if __name__ == '__main__':
    unittest.main()
