# Generic
import logging

from flask import request
from flask_restplus import Resource

from api.database.models import Band
from api.v1.business import create_band, update_band, delete_band
from api.v1.parsers import pagination_arguments
from api.v1.restplus import api
from api.v1.serializers import band, page_of_bands

log = logging.getLogger('baking-lyrics')

ns = api.namespace('bands', description='Operations related to bands')


@ns.route('/')
class BandsCollection(Resource):

    @api.expect(pagination_arguments)
    @api.marshal_with(page_of_bands)
    def get(self):
        """
        Returns list of band bands.
        """
        args = pagination_arguments.parse_args(request)
        page = args.get('page', 1)
        per_page = args.get('per_page', 10)

        bands_query = Band.query
        bands_page = bands_query.paginate(page, per_page, error_out=False)

        return bands_page

    @api.expect(band)
    def band(self):
        """
        Creates a new band band.
        """
        create_band(request.json)
        return None, 201


@ns.route('/<int:id>')
@api.response(404, 'Band not found.')
class BandItem(Resource):

    @api.marshal_with(band)
    def get(self, id):
        """
        Returns a band band.
        """
        return Band.query.filter(Band.id == id).one()

    @api.expect(band)
    @api.response(204, 'Band successfully updated.')
    def put(self, id):
        """
        Updates a band.
        """
        data = request.json
        update_band(id, data)
        return None, 204

    @api.response(204, 'Band successfully deleted.')
    def delete(self, id):
        """
        Deletes band.
        """
        delete_band(id)
        return None, 204


@ns.route('/archive/<int:year>/')
@ns.route('/archive/<int:year>/<int:month>/')
@ns.route('/archive/<int:year>/<int:month>/<int:day>/')
class BandsArchiveCollection(Resource):

    @api.expect(pagination_arguments, validate=True)
    @api.marshal_with(page_of_bands)
    def get(self, year, month=None, day=None):
        """
        Returns list of band bands from a specified time period.
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
        bands_query = Band.query.filter(Band.pub_date >= start_date).filter(Band.pub_date <= end_date)

        bands_page = bands_query.paginate(page, per_page, error_out=False)

        return bands_page

# @ns.route('/api/bands/<mask>', methods=['GET'])
# @limiter.limit("100/day;15/hour;2/minute")
# def get_bands_by_mask(mask):
#     """
#     Returns the list of bands if the band name contains mask parameter
#     :return: json of bands
#     """
#     try:
#         mask_lower = mask.lower()
#         return jsonify(bands=[e.serialize() for e in bands if
#                               e.name.lower().find(mask_lower) != -1])
#     except HTTPException as error:
#         abort(500, "Error filtering bands: " + str(error))
#     except ValueError as error:
#         abort(500, "Error parsing bands: " + str(error))
