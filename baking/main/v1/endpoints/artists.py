# Generic
import logging

# Libs
from flask import request
from flask_restplus import Resource
from flask_restplus import abort
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

# Own
from baking.main import api
from baking.main.database.models import Artist
from baking.main.v1.models.business import create_artist, update_artist, delete_artist
from baking.main.v1.parsers import pagination_arguments
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
        page = args.get('page', 1)
        per_page = args.get('per_page', 10)

        artists_query = Artist.query
        artists_page = artists_query.paginate(page, per_page, error_out=False)

        return artists_page

    @api.expect(artist)
    @api.response(404, 'Artist not found.')
    def post(self):
        """
        Creates a new artist.
        """
        try:
            create_artist(request.json)
        except AttributeError:
            abort(400, 'Bad request')

        return None, 201


@ns.route('/<int:artist_id>')
@api.response(404, 'Artist not found.')
class ArtistItem(Resource):

    @api.marshal_with(artist)
    def get(self, artist_id):
        """
        Returns a artist artist.
        """
        try:
            return Artist.query.filter(Artist.id == artist_id).one()
        except NoResultFound:
            abort(404, 'Artist not found.')

    @api.expect(artist)
    @api.response(204, 'Artist successfully updated.')
    def put(self, artist_id):
        """
        Updates a artist.
        """
        data = request.json
        update_artist(artist_id, data)
        return None, 204

    @api.response(204, 'Artist successfully deleted.')
    def delete(self, artist_id):
        """
        Deletes artist.
        """
        delete_artist(artist_id)
        return None, 204


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

        artists = Artist.query.filter(Artist.name.like('%' + partial_artist_name + '%'))
        artists = artists.order_by(Artist.name).all()

        if len(artists) == 0:
            abort(404, 'Artist not found')
        else:
            return artists


@ns.route('/random/<number_of_artists>')
@api.response(400, 'Number of artists between 6 and 20 is needed.')
@api.response(404, 'Famous artist not found.')
@api.response(404, 'Artist not found.')
class GetNRandomFamousArtists(Resource):

    @api.marshal_with(artist)
    def get(self, number_of_artists):
        """
        Returns a a list of <number_of_artists> random famous artists.
        """

        number_of_artists = int(number_of_artists)
        if number_of_artists < 6:
            abort(400, 'A minimum of 6 artists are to be retrieved.')
        if number_of_artists > 20:
            abort(400, 'A maximum of 20 artists are to be retrieved.')

        famous_artists = Artist.query.filter(Artist.cover == 1)  # Cover is 1 if artists should be on front page (cover)

        if len(famous_artists.all()) == 0:
            abort(404, 'No famous artists found')

        if len(famous_artists.all()) < number_of_artists:
            number_of_artists = len(famous_artists.all())

        artists = famous_artists.order_by(func.random()).all()[:number_of_artists]

        if len(artists) == 0:
            abort(404, 'No artists found')

        return artists


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
