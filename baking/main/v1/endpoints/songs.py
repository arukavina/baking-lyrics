
# Generic
import logging

# Libs
from flask_restx import Resource, abort
from sqlalchemy.exc import NoResultFound

# Own
from baking.main import api
from baking.main.database.models import Song
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


@ns.route('/<int:song_id>')
@ns.response(404, 'Song not found.')
class SongItem(Resource):

    @ns.marshal_with(song)
    def get(self, song_id):
        """
        Returns a song with a list of bands.
        """
        logger.debug('Getting song %s', song_id)
        try:
            return Song.query.filter(Song.id == song_id).one()
        except NoResultFound:
            abort(404, 'Song not found.')
