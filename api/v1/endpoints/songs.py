
# Generic
import logging

# Libs
from flask import request
from flask_restplus import Resource
from flask_restplus import abort

# Own
from api.database.models import Song
from api.v1.models.business import create_song, update_song, delete_song
from api.v1 import api
from api.v1.serializers import song

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


@ns.route('/<int:id>')
@ns.response(404, 'Song not found.')
class SongItem(Resource):

    @ns.marshal_with(song)
    def get(self, id):
        """
        Returns a song with a list of bands.
        """
        return Song.query.filter(Song.id == id).one()

    @ns.expect(song)
    @ns.response(204, 'Song successfully updated.')
    def put(self, id):
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
        update_song(id, data)
        return None, 204

    @ns.response(204, 'Song successfully deleted.')
    def delete(self, id):
        """
        Deletes a song.
        """
        delete_song(id)
