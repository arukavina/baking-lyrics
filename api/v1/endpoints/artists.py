# Generic
import logging

from flask import request
from flask_restplus import Resource

from api.database.models import Artist
from api.v1.models.business import create_artist, update_artist, delete_artist
from api.v1.parsers import pagination_arguments
from api.v1 import api
from api.v1.serializers import artist, page_of_artists

logger = logging.getLogger('baking-lyrics')

ns = api.namespace('artists', description='Operations related to artists')


@ns.route('/')
class ArtistsCollection(Resource):

    @api.expect(pagination_arguments)
    @api.marshal_with(page_of_artists)
    def get(self):
        """
        Returns list of artist artists.
        """
        args = pagination_arguments.parse_args(request)
        page = args.get('page', 1)
        per_page = args.get('per_page', 10)

        artists_query = Artist.query
        artists_page = artists_query.paginate(page, per_page, error_out=False)

        return artists_page

    @api.expect(artist)
    def post(self):
        """
        Creates a new artist.
        """
        create_artist(request.json)
        return None, 201


@ns.route('/<int:id>')
@api.response(404, 'Artist not found.')
class ArtistItem(Resource):

    @api.marshal_with(artist)
    def get(self, id):
        """
        Returns a artist artist.
        """
        return Artist.query.filter(Artist.id == id).one()

    @api.expect(artist)
    @api.response(204, 'Artist successfully updated.')
    def put(self, id):
        """
        Updates a artist.
        """
        data = request.json
        update_artist(id, data)
        return None, 204

    @api.response(204, 'Artist successfully deleted.')
    def delete(self, id):
        """
        Deletes artist.
        """
        delete_artist(id)
        return None, 204


@ns.route('/archive/<int:year>/')
@ns.route('/archive/<int:year>/<int:month>/')
@ns.route('/archive/<int:year>/<int:month>/<int:day>/')
class ArtistsArchiveCollection(Resource):

    @api.expect(pagination_arguments, validate=True)
    @api.marshal_with(page_of_artists)
    def get(self, year, month=None, day=None):
        """
        Returns list of artist artists from a specified time period.
        """
        args = pagination_arguments.parse_args(request)
        page = args.get('page', 1)
        per_page = args.get('per_page', 10)

        start_month = month if month else 1
        end_month = month if month else 12
        start_day = day if day else 1
        end_day = day + 1 if day else 31
        start_date = '{0:04d}-{1:02d}-{2:02d}'.format(year, start_month, start_day)
        end_date = '{0:04d}-{1:02d}-{2:02d}'.format(year, end_month, end_day)
        artists_query = Artist.query.filter(Artist.formation_date >= start_date).filter(Artist.formation_date <= end_date)

        artists_page = artists_query.paginate(page, per_page, error_out=False)

        return artists_page

# @ns.route('/api/artists/<mask>', methods=['GET'])
# @limiter.limit("100/day;15/hour;2/minute")
# def get_artists_by_mask(mask):
#     """
#     Returns the list of artists if the artist name contains mask parameter
#     :return: json of artists
#     """
#     try:
#         mask_lower = mask.lower()
#         return jsonify(artists=[e.serialize() for e in artists if
#                               e.name.lower().find(mask_lower) != -1])
#     except HTTPException as error:
#         abort(500, "Error filtering artists: " + str(error))
#     except ValueError as error:
#         abort(500, "Error parsing artists: " + str(error))
