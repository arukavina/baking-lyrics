# Generic
import unittest

# Libs
from flask_testing import TestCase

# Own
from baking.manage import app


class TestSongs(TestCase):
    def create_app(self):
        app.config.from_object('config.development')
        return app


class TestSongEndPoints(TestSongs):
    def test_song_create(self):
        import json
        
        id_testing = 362238
        headers = {'content-type': 'application/json'}
        data = {"title": "gloria", "lyrics": "gloria patri et filio et spiritui sancto, sicut erat in principio et nunc et semper et in saecula saeculorum amen", "pub_date": "1987-12-05T00:00:00", "artist_id": 18231, "country": "US"}
        
        response = self.client.post('api/v1/songs/', data = json.dumps(data), headers = headers)
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
        import json
        
        data =  {
                    "artist_id": 18231,
                    "title": "Amen",
                    "lyrics": "I heard from a friend of a friend of a friend that\nYou finally got rid of that girlfriend\nYou finally came out of that love coma boy\nI heard Mary Jane at the powder-puff beauty shop\nSayin' that blond in her tube top\nShe left our Jimmy for a boy in Illinois\nSomeone give me an amen,\nSomeone give me an amen.\nCan I get a thank God Hallelujah\nYou finally saw what she was doing to ya\nYour mama called it, she was right\nGlad to see you saw the light.\nWhole town yeah we hooped and hollered.\nShe drove away nobody stopped her\nNa na na na na, I'll say it again\nSomeone give me an amen.\nYeah right, like I really coulda said something\nYou wouldn't heard it if the train was coming\nYou had your head so high in the clouds\nOh I, I had a really good reason\nFor hiding my feelings but now I can finally spit it out\nSomeone give me an amen.\nSomeone give me an amen.\nCan I get a thank God Hallelujah\nYou finally saw what she was doing to ya\nYour mama called it, she was right\nGlad to see you saw the light.\nWhole town yeah we hooped and hollered.\nShe drove away nobody stopped her\nNa na na na na, I'll say it again\nSomeone give me an amen.\nI'm standing right here in front of you\nI think I love you too\nCan I get a thank God Hallelujah\nBaby do you believe it, do you?\nYour mama called it, she was right\nGlad to see you saw the light.\nWhole town yeah they hooped and hollered.\nThe preacher's son and the farmer's daughter.\nNa na na na na, I'll say it again\nSomeone give me an amen,\nSomeone give me an amen\nNa na na na na na na na na na na\nNa na na na na na na na na na na"
                }
        headers = {'content-type': 'application/json'}
        id_testing = 362238
        response = self.client.put('api/v1/songs/{}'.format(id_testing), data = json.dumps(data), headers = headers)
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 204)
        
    def test_song_delete(self):
        id_testing = 362238
        response = self.client.delete('api/v1/songs/{}'.format(id_testing))
        print('\n\nResponse: ' + str(response.status_code))
        self.assertEqual(response.status_code, 204)
        
if __name__ == '__main__':
    unittest.main()
