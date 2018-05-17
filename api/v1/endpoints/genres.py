
# Generic
import logging

# Libs
from flask import request
from flask_restplus import Resource

# Own
from api.database.models import Genre
from api.v1.models.business import create_genre, delete_genre, update_genre
from api.v1.restplus import api
from api.v1.serializers import genre, genres_with_bands

logger = logging.getLogger('baking-api')

ns = api.namespace('genres', description='Operations related to genres')


@ns.route('/')
class GenreCollection(Resource):

    @api.marshal_list_with(genres_with_bands)
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


@ns.route('/<int:id>')
@api.response(404, 'Genre not found.')
class GenreItem(Resource):

    @api.marshal_with(genre)
    def get(self, id):
        """
        Returns a genre with a list of band.
        """
        return Genre.query.filter(Genre.id == id).one()

    @api.expect(genre)
    @api.response(204, 'Genre successfully updated.')
    def put(self, id):
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
        update_genre(id, data)
        return None, 204

    @api.response(204, 'Genre successfully deleted.')
    def delete(self, id):
        """
        Deletes a genre.
        """
        delete_genre(id)
