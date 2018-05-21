
# Generic
import logging

# Libs
from flask import request
from flask import current_app
from flask_restplus import Resource
from flask_restplus import abort

# Own
from api.database.models import Song, Artist
from api.v1.models.business import create_song
from api.v1.restplus import api
from api.v1.serializers import song

logger = logging.getLogger('baking-api')
ns = api.namespace('songs', description='Operations related to the songs generation')

# TODO: Move to app cache.
current_songs_model = None
current_title_model = None
current_songs_model_name = None
current_title_model_name = None


@ns.route('/')
class SongCollection(Resource):

    @ns.marshal_list_with(song)
    def get(self):
        """
        Returns list of songs
        """
        songs = Song.query.all()
        return songs

    @ns.response(201, 'Song successfully created.')
    @ns.expect(song)
    def post(self):
        """
        Creates a new song.
        """
        data = request.json
        create_song(data)
        return None, 201


@ns.route('/<int:id>')
@ns.response(404, 'Song not found.')
class SongItem(Resource):

    @ns.marshal_with(song)
    def get(self, id):
        """
        Returns a song with a list of bands.
        """
        return Song.query.filter(Song.id == id).one()

    # @ns.expect(song)
    # @ns.response(204, 'Song successfully updated.')
    # def put(self, id):
    #     """
    #     Updates a song.
    #     Use this method to change the name of a song.
    #     * Send a JSON object with the new name in the request body.
    #     ```
    #     {
    #       "name": "New Song Name"
    #     }
    #     ```
    #     * Specify the ID of the song to modify in the request URL path.
    #     """
    #     data = request.json
    #     update_song(id, data)
    #     return None, 204
    #
    # @ns.response(204, 'Song successfully deleted.')
    # def delete(self, id):
    #     """
    #     Deletes a song.
    #     """
    #     delete_song(id)


@ns.route('/generate/<lang>/words/<int:number_words>/')
@ns.route('/generate/<lang>/words/<int:number_words>/bands/<int:band_id>/')
@ns.response(404, 'Artist not found.')
@ns.response(500, 'Internal server error.')
class SongItem(Resource):

    @ns.marshal_with(song)
    def get(self, lang='es', number_words=0, band_id=None):
        """
        Returns a generated song for the required band.
        """
        return Artist.query.filter(Song.id == band_id).one()
        # band = Artist.query.filter(Song.id == band_id).one()
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

    if current_model_class == 'SongsLSTMModel':

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
