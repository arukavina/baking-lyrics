
# Generic
import logging

# Libs
from flask import request
from flask_restplus import Resource
from flask_restplus import abort
from sqlalchemy.orm.exc import NoResultFound

# Own
from baking.main import api
from baking.main.database.models import Genre
from baking.main.v1.models.business import create_genre, delete_genre, update_genre
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

    @api.response(201, 'Genre successfully created.')
    @api.expect(genre)
    def post(self):
        """
        Creates a new genre.
        """
        data = request.json
        create_genre(data)
        return None, 201


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

    @api.expect(genre)
    @api.response(204, 'Genre successfully updated.')
    def put(self, genre_id):
        """
        Updates a genre.
        Use this method to change the name of a genre.
        * Send a JSON object with the new name in the request body.
        ```
        {
          "name": "New Genre Name"
        }
        ```
        * Specify the ID of the genre to modify in the request URL path.
        """
        data = request.json
        update_genre(genre_id, data)
        return None, 204

    @api.response(204, 'Genre successfully deleted.')
    def delete(self, genre_id):
        """
        Deletes a genre.
        """
        delete_genre(genre_id)
        return None, 204
