
# Generic
import logging

# Libs
from flask_restx import Resource, abort
from sqlalchemy.exc import NoResultFound

# Own
from baking.main import api
from baking.main.database.models import Genre
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
        genres = Genre.query.all()
        return genres


@ns.route('/<int:genre_id>')
@api.response(404, 'Genre not found.')
class GenreItem(Resource):

    @api.marshal_with(genre)
    def get(self, genre_id):
        """
        Returns a genre with a list of band.
        """
        try:
            return Genre.query.filter(Genre.id == genre_id).one()
        except NoResultFound:
            abort(404, 'Genre not found.')
