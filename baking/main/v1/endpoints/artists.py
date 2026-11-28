# Generic
import logging
import random
from datetime import datetime, timedelta

# Libs
from flask import request
from flask_restx import Resource, abort

# Own
from baking.main import api
from baking.main.repository import get_repository
from baking.main.v1.parsers import paginate, pagination_arguments
from baking.main.v1.serializers import artist, page_of_artists

logger = logging.getLogger('baking-api')

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
        return paginate(get_repository().list_artists(), args.get('page', 1), args.get('per_page', 10))


@ns.route('/<int:artist_id>')
@api.response(404, 'Artist not found.')
class ArtistItem(Resource):

    @api.marshal_with(artist)
    def get(self, artist_id):
        """
        Returns a artist artist.
        """
        found = get_repository().get_artist(artist_id)
        if found is None:
            abort(404, 'Artist not found.')
        return found


@ns.route('/search/<partial_artist_name>')
@api.response(404, 'Artist not found.')
@api.response(400, 'A minimum of 3 characters are needed.')
class GetArtistByName(Resource):

    @api.marshal_with(artist)
    def get(self, partial_artist_name):
        """
        Returns a artist artist.
        """

        if len(partial_artist_name) < 3:
            abort(400, 'A minimum of 3 characters are needed.')

        artists = get_repository().search_artists(partial_artist_name)

        if len(artists) == 0:
            abort(404, 'Artist not found')
        return artists


@ns.route('/random/<int:number_of_artists>')
@api.response(400, 'Number of artists between 6 and 20 is needed.')
@api.response(404, 'Famous artist not found.')
@api.response(404, 'Artist not found.')
class GetNRandomFamousArtists(Resource):

    @api.marshal_with(artist)
    def get(self, number_of_artists):
        """
        Returns a a list of <number_of_artists> random famous artists.
        """

        if number_of_artists < 6:
            abort(400, 'A minimum of 6 artists are to be retrieved.')
        if number_of_artists > 20:
            abort(400, 'A maximum of 20 artists are to be retrieved.')

        famous_artists = get_repository().cover_artists()  # cover artists are the front page ones

        if len(famous_artists) == 0:
            abort(404, 'No famous artists found')

        return random.sample(famous_artists, min(number_of_artists, len(famous_artists)))


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

        # Half-open interval [start_date, end_date)
        try:
            if day is not None:
                start_date = datetime(year, month, day)
                end_date = start_date + timedelta(days=1)
            elif month is not None:
                start_date = datetime(year, month, 1)
                end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
            else:
                start_date = datetime(year, 1, 1)
                end_date = datetime(year + 1, 1, 1)
        except ValueError:
            abort(400, 'Invalid date.')

        artists = [a for a in get_repository().list_artists()
                   if a['formation_date'] is not None and start_date <= a['formation_date'] < end_date]

        return paginate(artists, args.get('page', 1), args.get('per_page', 10))
