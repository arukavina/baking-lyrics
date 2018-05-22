# Generic
import logging

# Libs
from flask import current_app
from flask_restplus import Resource
from flask_restplus import abort

# Own
from api.database.models import ArtificialSong, Artist
from api.v1.restplus import api
from api.v1.serializers import song

logger = logging.getLogger('baking-api')
ns = api.namespace('artificial_songs', description='Operations related to artificially generated songs')

# TODO: Move to app cache.
current_songs_model = None
current_title_model = None
current_songs_model_name = None
current_title_model_name = None


@ns.route('/')
class ArtificialSongCollection(Resource):

    @ns.marshal_list_with(song)
    def get(self):
        """
        Returns list of generated songs
        """
        songs = ArtificialSong.query.all()
        return songs


@ns.route('/<int:id>')
@ns.response(404, 'ArtificialSong not found.')
class ArtificialSongItem(Resource):

    @ns.marshal_with(song)
    def get(self, id):
        """
        Returns a existing generated song.
        """
        return ArtificialSong.query.filter(ArtificialSong.id == id).one()


@ns.route('/generate/<lang>/words/<int:number_words>/')
@ns.route('/generate/<lang>/words/<int:number_words>/artist/<int:artist_id>/')
@ns.response(404, 'Artist not found.')
@ns.response(500, 'Internal server error.')
class ArtificialSongItem(Resource):

    @ns.marshal_with(song)
    def get(self, lang='es', number_words=0, artist_id=None):
        """
        Returns a generated song for the lang, words and artist_id
        """
        return Artist.query.filter(ArtificialSong.id == artist_id).one()
        # band = Artist.query.filter(ArtificialSong.id == band_id).one()
#         if band is None:
#             logger.error('Not able to instantiate band: {}'.format(band_id))
#             return render_template('500.htm'), 500
#
#         global current_songs_model
#         global current_title_model
#         global current_songs_model_name
#         global current_title_model_name
#
#         try:
#             lang = lang.lower()
#             number_words = int(number_words)
#             model = str('current')
#
#             # if words is not None:
#             #     words = str(words).split(' ')
#             # else:
#             #     words = []
#
#             # Handling models
#             if not model != 'current':
#                 abort(400, "Model not valid: {}".format(model))
#
#             elif model == 'current':
#                 logger.info("Using cached default models...")
#
#                 current_songs_model.__str__()
#                 current_title_model.__str__()
#
#             elif model == current_songs_model_name:
#                 logger.info("Using cached models...")
#
#                 current_songs_model.__str__()
#                 current_title_model.__str__()
#
#             else:
#
#                 logger.info("Loading {} models...".format(model))
#
#                 current_songs_model_name = model
#
#                 _ModelClass, args = get_model_class(model)
#
#                 current_songs_model = _ModelClass(**args)
#                 current_songs_model.__str__()
#
#                 logger.info("{} songs models initialized correctly".format(current_songs_model))
#
#             songs = ""
#
#             try:
#                 songs = current_songs_model.generate_sentence(lang, number_words, 69, words)
#             except NotImplementedError:
#                 abort(501, "Not implemented error: " + str(model))
#
#             return jsonify(songs)
#         except HTTPException as error:
#             abort(500, "Error generating songs: " + str(error))
#         except ValueError as error:
#             abort(500, "Error parsing songs: " + str(error))
#


def get_model_class(model):
    """

    :param model:
    :return:
    """

    import importlib

    current_model_class = current_app.config[str(model).upper()]

    if current_model_class == 'ArtificialSongsLSTMModel':

        args = dict(
            model_file_path=current_app.config["LYRICS_LSTM_MODEL_FILE_PATH"],
            weights_file_path=current_app.config["LYRICS_LSTM_WEIGHTS_FILE_PATH"],
            seed_file_path=current_app.config["LYRICS_LSTM_SEED_FILE_PATH"]
            )

        _ModelClass = getattr(importlib.import_module("api.ml_models"), current_model_class)
        return _ModelClass, args

    elif current_model_class == 'TitleLSTMModel':

        args = dict(
            model_file_path=current_app.config["TITLE_LSTM_MODEL_FILE_PATH"],
            tokenizer_file_path=current_app.config["TITLE_LSTM_TOKENIZER_FILE_PATH"]
        )

        _ModelClass = getattr(importlib.import_module("api.ml_models"), current_model_class)
        return _ModelClass, args

    elif current_model_class == 'NGramsModel':
        abort(501, "Not implemented models class: " + str(current_model_class))

    else:
        abort(501, "Not implemented models class: " + str(current_model_class))
