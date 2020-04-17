# Generic
import unittest

# Libs
from flask_testing import TestCase

# Own
from baking.manage import app
#from flask import current_app as app


class TestArtists(TestCase):
    def create_app(self):
        app.config.from_object('config.testing')
        return app


class TestArtistEndPoints(TestArtists):
    def test_artist_create(self):
        import json

        headers = {'content-type': 'application/json'}
        data = {"name": "Nichi", "pub_date": "1987-12-05T00:00:00", "genre_id": 1, "country": "US"}

        response = self.client.post('api/v1/artists/', data=json.dumps(data), headers=headers)
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 201)

    def test_artist_get(self):
        from baking.main.database.models import Artist
        from baking.main.v1.endpoints.artists import artist
        from flask_restplus import marshal

        id_testing = 1
        g = marshal(Artist.query.filter(Artist.id == id_testing).one(), artist)

        response = self.client.get('/api/v1/artists/{}'.format(id_testing))
        print('\n\nResponse: ' + str(response.json))
        self.assertEqual(response.json, g)

    def test_artist_update(self):
        import json

        data = {"name": "beyonce-knowles", "pub_date": "1987-12-05T00:00:00", "genre_id": 1, "country": "US"}
        headers = {'content-type': 'application/json'}
        id_testing = 1
        response = self.client.put('api/v1/artists/{}'.format(id_testing), data=json.dumps(data), headers=headers)
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 204)

    def test_artist_delete(self):
        from baking.main.database.models import Artist
        from baking.main import db

        id_testing = db.session.query(db.func.max(Artist.id)).scalar()
        response = self.client.delete('api/v1/artists/{}'.format(id_testing))
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 204)

    def test_artist_get_by_name(self):
        partial_artist_name = 'monroe'
        response = self.client.get('/api/v1/artists/search/{}'.format(partial_artist_name))
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 200)

    def test_artist_get_archive(self):
        archive_date = '1987/12/05/'
        response = self.client.get('/api/v1/artists/archive/{}'.format(archive_date))
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 200)

    def test_artist_get_all(self):
        response = self.client.get('/api/v1/artists/')
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
