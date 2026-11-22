# Generic
import logging

# Libs
from flask import current_app
from flask_restx import Resource, abort
from sqlalchemy.exc import NoResultFound

# Own
from baking.main import api, db
from baking.main.database.models import ArtificialSong, ArtificialTitle, utcnow
from baking.main.v1.models.models_manager import ModelsManager
from baking.main.v1.serializers import artificial_title

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
@ns.response(404, 'Artificial song not found.')
@ns.response(500, 'Internal server error.')
@ns.response(503, 'ML models are not loaded.')
class ArtificialTitleItem(Resource):

    @ns.marshal_with(artificial_title)
    def get(self, song_id, lang='en'):
        """
        Returns a generated title for the required lang and song_id.
        """
        if lang != 'en':
            abort(400, 'Artificial Titles can only be generated in english')

        try:
            lyrics_text = ArtificialSong.query.filter(ArtificialSong.id == song_id).one().lyrics

            if not current_app.extensions.get('ml_available', False):
                abort(503, 'ML models are not loaded')

            model = ModelsManager().get_model('titles')
            title_text = model.generate_sentence(input_text=lyrics_text)

            at = ArtificialTitle(
                title=title_text,
                creation_date=utcnow()
            )

            db.session.add(at)

            db.session.commit()

            return at
        except NoResultFound:
            abort(404, 'Artificial song does not exist.')
        except FileNotFoundError as e:
            logger.error(e)
            abort(500, 'Internal Server error, please check log.')

