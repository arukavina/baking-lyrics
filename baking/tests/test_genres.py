# Generic
import unittest

# Libs
from flask_testing import TestCase

# Own
from baking.manage import app


class TestGenres(TestCase):
    def create_app(self):
        app.config.from_object('config.development')
        return app


class TestGenreEndPoints(TestGenres):
    def test_genre_create(self):
        import json
        
        headers = {'content-type': 'application/json'}
        data = {"id": 18232, "name": "Death Metal"}
        
        response = self.client.post('api/v1/genres/', data = json.dumps(data), headers = headers)
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 201)   
        
    def test_genre_get(self):

        from baking.main.database.models import Genre
        from baking.main.v1.endpoints.genres import genre
        from flask_restplus import marshal

        id_testing = 1
        g = marshal(Genre.query.filter(Genre.id == id_testing).one(), genre)

        response = self.client.get('/api/v1/genres/{}'.format(id_testing))
        print('\n\nResponse: ' + str(response.json))
        self.assertEqual(response.json, g)
        
    def test_genre_update(self):
        import json
        
        data =  {"name": "country"}
        headers = {'content-type': 'application/json'}
        id_testing = 18232
        response = self.client.put('api/v1/genres/{}'.format(id_testing), data = json.dumps(data), headers = headers)
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 204)
        
    def test_genre_delete(self):
        id_testing = 18232
        response = self.client.delete('api/v1/genres/{}'.format(id_testing))
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 204)
        
if __name__ == '__main__':
    unittest.main()
