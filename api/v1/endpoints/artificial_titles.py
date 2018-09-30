# Generic
import logging

# Libs
from flask import current_app
from flask_restplus import Resource

# Own
from api.v1 import api
from api.v1.serializers import artificial_title
from api.database.models import ArtificialTitle
from api.database.models import Song
from api.v1.models.models_manager import ModelsManager

logger = logging.getLogger('baking-api')
ns = api.namespace('artificial_titles', description='Operations related to artificially generated titles')


@ns.route('/')
class ArtificialTitleCollection(Resource):

    @ns.marshal_list_with(artificial_title)
    def get(self):
        """
        Returns list of generated titles
        """
        titles = ArtificialTitle.query.all()
        return titles


@ns.route('/generate/<lang>/song/<int:song_id>/')
@ns.response(404, 'Song not found.')
@ns.response(500, 'Internal server error.')
class ArtificialTitleItem(Resource):

    @ns.marshal_with(artificial_title)
    def get(self, song_id, lang='en'):
        """
        Returns a generated title for the required lang and song_id.
        """
        model = ModelsManager().get_model('titles')
        lyrics_text = Song.query.filter(Song.id == song_id).one().lyrics
        title_text = model.generate_sentence(input_text=lyrics_text)
        return ArtificialTitle(title_text)
