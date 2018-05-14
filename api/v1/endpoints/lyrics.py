
# Generic
import logging

# Libs
from flask import request
from flask_restplus import Resource

# Own
from api.database.models import Lyric
from api.v1.business import create_lyric
from api.v1.restplus import api
from api.v1.serializers import lyric

log = logging.getLogger('baking-api')

ns = api.namespace('lyrics', description='Operations related to lyrics')


@ns.route('/')
class LyricCollection(Resource):

    @api.marshal_list_with(lyric)
    def get(self):
        """
        Returns list of lyrics
        """
        lyrics = Lyric.query.all()
        return lyrics

    @api.response(201, 'Lyric successfully created.')
    @api.expect(lyric)
    def post(self):
        """
        Creates a new lyric.
        """
        data = request.json
        create_lyric(data)
        return None, 201


@ns.route('/<int:id>')
@api.response(404, 'Lyric not found.')
class LyricItem(Resource):

    @api.marshal_with(lyric)
    def get(self, id):
        """
        Returns a lyric with a list of band.
        """
        return Lyric.query.filter(Lyric.id == id).one()

    # @api.expect(lyric)
    # @api.response(204, 'Lyric successfully updated.')
    # def put(self, id):
    #     """
    #     Updates a lyric.
    #     Use this method to change the name of a lyric.
    #     * Send a JSON object with the new name in the request body.
    #     ```
    #     {
    #       "name": "New Lyric Name"
    #     }
    #     ```
    #     * Specify the ID of the lyric to modify in the request URL path.
    #     """
    #     data = request.json
    #     update_lyric(id, data)
    #     return None, 204
    #
    # @api.response(204, 'Lyric successfully deleted.')
    # def delete(self, id):
    #     """
    #     Deletes a lyric.
    #     """
    #     delete_lyric(id)
