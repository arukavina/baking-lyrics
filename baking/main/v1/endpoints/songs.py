# Generic
import logging

# Libs
from flask_restx import Resource, abort

# Own
from baking.main import api
from baking.main.repository import get_repository
from baking.main.v1.serializers import song, song_view

logger = logging.getLogger('baking-api')
ns = api.namespace('songs', description='Operations related to songs')


@ns.route('/')
class SongCollection(Resource):

    @ns.marshal_list_with(song)
    def get(self):
        """
        Returns list of songs
        """
        return [song_view(found) for found in get_repository().list_songs()]


@ns.route('/<int:song_id>')
@ns.response(404, 'Song not found.')
class SongItem(Resource):

    @ns.marshal_with(song)
    def get(self, song_id):
        """
        Returns a song with a list of bands.
        """
        logger.debug('Getting song %s', song_id)
        found = get_repository().get_song(song_id)
        if found is None:
            abort(404, 'Song not found.')
        return song_view(found)
