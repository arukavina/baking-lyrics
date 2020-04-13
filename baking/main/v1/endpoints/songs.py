
# Generic
import logging

# Libs
from flask import request
from flask_restplus import Resource
from flask_restplus import abort
from sqlalchemy.orm.exc import NoResultFound

# Own
from baking.main import api
from baking.main.database.models import Song
from baking.main.v1.models.business import create_song, update_song, delete_song
from baking.main.v1.serializers import song

logger = logging.getLogger('baking-api')
ns = api.namespace('songs', description='Operations related to songs')


@ns.route('/')
class SongCollection(Resource):

    @ns.marshal_list_with(song)
    def get(self):
        """
        Returns list of songs
        """
        songs = Song.query.all()
        return songs

    @ns.response(201, 'Song successfully created.')
    @ns.expect(song)
    def post(self):
        """
        Creates a new song.
        """
        data = request.json
        create_song(data)
        return None, 201


@ns.route('/<int:song_id>')
@ns.response(404, 'Song not found.')
class SongItem(Resource):

    @ns.marshal_with(song)
    def get(self, song_id):
        """
        Returns a song with a list of bands.
        """
        print('Getting song')
        try:
            return Song.query.filter(Song.id == song_id).one()
        except NoResultFound:
            abort(404, 'Song not found.')

    @ns.expect(song)
    @ns.response(204, 'Song successfully updated.')
    def put(self, song_id):
        """
        Updates a song.
        Use this method to change the name of a song.
        * Send a JSON object with the new name in the request body.
        ```
        {
          "name": "New Song Name"
        }
        ```
        * Specify the ID of the song to modify in the request URL path.
        """
        data = request.json
        update_song(song_id, data)
        return None, 204

    @ns.response(204, 'Song successfully deleted.')
    def delete(self, song_id):
        """
        Deletes a song.
        """
        delete_song(song_id)
        return None, 204

