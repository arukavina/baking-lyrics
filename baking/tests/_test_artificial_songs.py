# Generic
import unittest

# Libs
from flask_testing import TestCase

# Own
from flask import current_app as app


class TestArtificialSongs(TestCase):
    def create_app(self):
        app.config.from_object('config.default')
        app.config.from_object('config.testing')
        return app


class TestArtificialSongEndPoints(TestArtificialSongs):
    def test_artificial_song_with_seed_get(self):
        self.create_app()
        seed = 1234
        words = 100
        artist = 1
        response = self.client.get('/api/v1/artificial_songs/generate/en/seed/{}/words/{}/artist/{}/'.format(seed, words, artist))
        print('\n\nResponse (test_artificial_song_with_seed_get): ' + str(response.status_code))
        self.assertEqual(response.status_code, 200)

    def test_artificial_song_no_seed_get(self):
        self.create_app()
        words = 100
        artist = 1
        response = self.client.get('/api/v1/artificial_songs/generate/en/words/{}/artist/{}/'.format(words, artist))
        print('\n\nResponse (test_artificial_song_no_seed_get): ' + str(response.status_code))
        self.assertEqual(response.status_code, 200)

    def test_all_artificial_songs_get(self):
        response = self.client.get('/api/v1/artificial_songs/')
        print('\n\nResponse (test_all_artificial_songs_get): ' + str(response.status_code))
        self.assertEqual(response.status_code, 200)

    def test_one_artificial_songs_get(self):
        artificial_song_id = 1
        response = self.client.get('/api/v1/artificial_songs/{}'.format(artificial_song_id))
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
