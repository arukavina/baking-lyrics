# Generic
import logging

# Libs
from flask import request
from flask_restx import Resource, abort

# Own
from baking.main import api
from baking.main.repository import get_repository
from baking.main.v1.parsers import page_of, pagination_arguments
from baking.main.v1.serializers import page_of_songs, song, song_view

logger = logging.getLogger('baking-api')
ns = api.namespace('songs', description='Operations related to songs')


@ns.route('/')
class SongCollection(Resource):

    @api.expect(pagination_arguments)
    @ns.marshal_with(page_of_songs)
    def get(self):
        """
        Returns a page of songs ordered by id.
        """
        args = pagination_arguments.parse_args(request)
        page, per_page = args.get('page', 1), args.get('per_page', 10)
        songs, total = get_repository().page_songs(page, per_page)
        return page_of([song_view(found) for found in songs], total, page, per_page)


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
