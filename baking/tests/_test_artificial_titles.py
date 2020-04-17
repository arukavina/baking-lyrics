# Generic
import unittest

# Libs
from flask_testing import TestCase

# Own
#from baking.manage import app
from flask import current_app as app


class TestArtificialTitles(TestCase):
    def create_app(self):
        app.config.from_object('config.development')
        return app


class TestArtificialTitleEndPoints(TestArtificialTitles):
    '''
    def test_artificial_title_get(self):
        artificial_song_id = 1
        response = self.client.get('/api/v1/artificial_titles/generate/en/song/{}/'.format(artificial_song_id))
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 200)
    '''
        
    def test_all_artificial_titles_get(self):
        response = self.client.get('/api/v1/artificial_titles/')
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 200)
        
if __name__ == '__main__':
    unittest.main()
