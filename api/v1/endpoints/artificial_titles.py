# Generic
import logging
from datetime import datetime

# Libs
from flask_restplus import Resource, abort
from sqlalchemy.orm.exc import NoResultFound

# Own
from api.v1 import api, db
from api.v1.serializers import artificial_title
from api.v1.models.models_manager import ModelsManager
from api.database.models import ArtificialTitle, ArtificialSong

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
class ArtificialTitleItem(Resource):

    @ns.marshal_with(artificial_title)
    def get(self, song_id, lang='en'):
        """
        Returns a generated title for the required lang and song_id.
        """

        model = ModelsManager().get_model('titles')

        # TODO: When available change bny ArtificialSong

        try:
            lyrics_text = ArtificialSong.query.filter(ArtificialSong.id == song_id).one().lyrics
            title_text = model.generate_sentence(input_text=lyrics_text)

            at = ArtificialTitle(
                title=title_text,
                creation_date=datetime.utcnow()
            )

            db.session.add(at)

            db.session.commit()

            return at
        except NoResultFound:
            abort(404, 'Artificial song does not exist.')
        except FileNotFoundError as e:
            logger.error(e)
            abort(500, 'Internal Server error, please check log.')

