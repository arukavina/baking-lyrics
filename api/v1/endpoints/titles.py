
# Generic
import logging

# Libs
from flask import request
from flask import current_app
from flask_restplus import Resource
from flask_restplus import abort

# Own
from api.v1.restplus import api
from api.v1.serializers import title
from api.database.models import Song

logger = logging.getLogger('baking-api')
ns = api.namespace('titles', description='Operations related to the titles generation')

# TODO: Move to app cache.
current_titles_model = None
current_title_model = None
current_titles_model_name = None
current_title_model_name = None


@ns.route('/')
class TitleCollection(Resource):

    @ns.marshal_list_with(title)
    def get(self):
        """
        Returns list of titles
        """
        titles = dict(body="let it be", lyrics=Song.query.filter(Song.id == 1).one())
        return titles

    @ns.response(201, 'Title successfully created.')
    @ns.expect(title)
    def post(self):
        """
        Creates a new title.
        """
        data = request.json
        # create_title(data)
        return None, 201


@ns.route('/generate/<lang>/lyrics/<int:lyric_id>/')
@ns.response(404, 'Song not found.')
@ns.response(500, 'Internal server error.')
class TitleItem(Resource):

    @ns.marshal_with(title)
    def get(self, lyric_id, lang='es'):
        """
        Returns a generated title for the required lyric id.
        """
        return "" # Title.query.filter(Song.id == lyric_id).one()
