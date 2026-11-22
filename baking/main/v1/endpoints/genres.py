# Generic
import logging

# Libs
from flask_restx import Resource, abort

# Own
from baking.main import api
from baking.main.repository import get_repository
from baking.main.v1.serializers import genre, genres_with_artists

logger = logging.getLogger('baking-api')

ns = api.namespace('genres', description='Operations related to genres')


@ns.route('/')
class GenreCollection(Resource):

    @api.marshal_list_with(genres_with_artists)
    def get(self):
        """
        Returns list of genres
        """
        repository = get_repository()
        artists_by_genre = {}
        for found in repository.list_artists():
            artists_by_genre.setdefault(found['genre_id'], []).append(found)
        return [{**found, 'artists': artists_by_genre.get(found['id'], [])} for found in repository.list_genres()]


@ns.route('/<int:genre_id>')
@api.response(404, 'Genre not found.')
class GenreItem(Resource):

    @api.marshal_with(genre)
    def get(self, genre_id):
        """
        Returns a genre with a list of band.
        """
        found = get_repository().get_genre(genre_id)
        if found is None:
            abort(404, 'Genre not found.')
        return found
