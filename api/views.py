#!/usr/bin/env python
"""
Flask End-Point
"""

# Generic
import logging
import random

# Libs
from flask import abort
from flask import request
from flask import jsonify

from werkzeug.exceptions import HTTPException

from api.v1.restplus import api
from api.v1.restplus import limiter
from api.util import log_utils
from api.util import http_handler as http

log = logging.getLogger('baking-lyrics')

ns = api.namespace('', description='Base operations')

# Global Objects:

bands = []
current_lyrics_model = None
current_title_model = None
current_lyrics_model_name = None
current_title_model_name = None

_valid_models = {
    'current': 'Current_Model',
    'lstm': 'LSTMModel',
    'ngrams': 'NGramsModel'
}

logger = log_utils.get_logger('baking-api')


@ns.before_first_request
def load_current_models():
    """
    Loads current models into memory
    :return: None
    """
    try:
        lyrics_model = api.config["CURRENT_MODEL_LYRICS"]
        title_model = api.config["CURRENT_MODEL_TITLE"]

        global current_lyrics_model
        global current_title_model
        global current_lyrics_model_name
        global current_title_model_name

        _ModelClass_lyrics, args_lyrics = get_model_class(lyrics_model)
        _ModelClass_title, args_title = get_model_class(lyrics_model)

        current_lyrics_model = _ModelClass_lyrics(**args_lyrics)
        current_title_model = _ModelClass_title(**args_title)

        current_lyrics_model.__str__()
        current_title_model.__str__()

        current_lyrics_model_name = lyrics_model
        current_title_model_name = lyrics_model

        logger.info("{} lyrics_model initialized correctly!".format(lyrics_model))
        logger.info("{} title_model initialized correctly!".format(title_model))

    except FileNotFoundError as error:
        abort(500, "Missing required files" + str(error))
    except OSError:
        abort(500, "Internal Server error")


@ns.before_request
def log_user_agent_info():
    """
    Logs uer agent info
    :return: None
    """
    values = '[{}] with {} - Request.Values: '.format(request.remote_addr,
                                                      request.headers.get('User-Agent'))
    if len(request.values) == 0:
        values += '(None)'
    for key in request.values:
        values += '{}: {}, '.format(key, request.values[key])
    logger.info(values)


@ns.route("/")
def index():
    return render_template("index.html")


@ns.route("/hello")
def hello():
    return get_random_lyric()


@ns.route('/api/models/<model>/lyrics/<lang>/<length>/<words>/bands/<band>', methods=['GET'])
@limiter.limit("100/day;15/hour;2/minute")
def get_lyrics_by_band(model, lang, length, words, band):
    """
    Returns a list of the list of <length> words in <lang> using the list of words <words>.
    Using Current model

    :param model: model to be used
    :param lang: language of model to use
    :param length: int, number of characters to generate
    :param words: list of words to use as a seed
    :param band: band Name
    :return: string

    """
    try:
        lang = lang.lower()
        length = int(length)
        band = str(band)
        model = str(model)

        if not validate_model(model):
            abort(400, "Model not valid: {}".format(model))

        model = _valid_models[model]

        if words is not None:
            words = str(words).split(' ')
        else:
            words = []

        _ModelClass, args = get_model_class(model)

        model_instance = _ModelClass(**args)
        model_instance.__str__()

        logger.info("{} model initialized correctly".format(model))

        lyrics = ""

        try:
            lyrics = model_instance.generate_sentence(lang, length, 69, words, band)
        except NotImplementedError as e:
            abort(501, "Not implemented error: " + str(model))

        return jsonify(lyrics)
    except HTTPException as error:
        abort(500, "Error generating lyrics: " + str(error))
    except ValueError as error:
        abort(500, "Error parsing lyrics: " + str(error))


@ns.route('/api/models/<model>/lyrics/<lang>/<length>/<words>', methods=['GET'])
@limiter.limit("100/day;15/hour;2/minute")
def get_lyrics(model, lang, length, words):
    """
    Returns a list of the list of <length> words in <lang> using the list of words <words>.
    Using Current model

    :param model: model to be used
    :param lang: language of model to use
    :param length: int, number of characters to generate
    :param words: list of words to use as a seed
    :return: string

    """

    global current_lyrics_model
    global current_title_model
    global current_lyrics_model_name
    global current_title_model_name

    try:
        lang = lang.lower()
        length = int(length)
        words = str(words)
        model = str(model)

        if words is not None:
            words = str(words).split(' ')
        else:
            words = []

        # Handling models
        if not validate_model(model):
            abort(400, "Model not valid: {}".format(model))

        if model == 'current':
            logger.info("Using cached default models...")

            current_lyrics_model.__str__()
            current_title_model.__str__()

        elif model == current_lyrics_model_name:
            logger.info("Using cached models...")

            current_lyrics_model.__str__()
            current_title_model.__str__()

        else:

            logger.info("Loading {} model...".format(model))

            current_lyrics_model_name = model

            model = _valid_models[model]

            _ModelClass, args = get_model_class(model)

            current_lyrics_model = _ModelClass(**args)
            current_lyrics_model.__str__()

            logger.info("{} lyrics model initialized correctly".format(current_lyrics_model))

        lyrics = ""

        try:
            lyrics = current_lyrics_model.generate_sentence(lang, length, 69, words)
        except NotImplementedError:
            abort(501, "Not implemented error: " + str(model))

        return jsonify(lyrics)
    except HTTPException as error:
        abort(500, "Error generating lyrics: " + str(error))
    except ValueError as error:
        abort(500, "Error parsing lyrics: " + str(error))


@ns.errorhandler(400)
def bad_request_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(400, error)
    return error_object.return_json_http(), error_object.code


@ns.errorhandler(404)
def not_found_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(404, error)
    return error_object.return_json_http(), error_object.code


@ns.errorhandler(500)
def internal_server_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(500, error)
    return error_object.return_json_http(), error_object.code


@ns.errorhandler(501)
def not_implemented_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(501, error)
    return error_object.return_json_http(), error_object.code


@ns.errorhandler(503)
def service_unavailable(error):
    logger.error(str(error))
    error_object = http.HttpHandler(503, error)
    return error_object.return_json_http(), error_object.code


def validate_model(model_name):
    """
    @deprecated... Please remove
    :param model_name:
    :return:
    """
    return model_name in _valid_models


def get_model_class(model):
    """

    :param model:
    :return:
    """

    import importlib

    current_model_class = api.config[str(model).upper()]

    if current_model_class == 'LyricsLSTMModel':

        args = dict(
            model_file_path=api.config["LYRICS_LSTM_MODEL_FILE_PATH"],
            weights_file_path=api.config["LYRICS_LSTM_WEIGHTS_FILE_PATH"],
            seed_file_path=api.config["LYRICS_LSTM_SEED_FILE_PATH"]
            )

        _ModelClass = getattr(importlib.import_module("api.ml_models"), current_model_class)
        return _ModelClass, args

    elif current_model_class == 'TitleLSTMModel':

        args = dict(
            model_file_path=api.config["TITLE_LSTM_MODEL_FILE_PATH"],
            tokenizer_file_path=api.config["TITLE_LSTM_TOKENIZER_FILE_PATH"]
        )

        _ModelClass = getattr(importlib.import_module("api.ml_models"), current_model_class)
        return _ModelClass, args

    elif current_model_class == 'NGramsModel':
        abort(501, "Not implemented model class: " + str(current_model_class))

    else:
        abort(501, "Not implemented model class: " + str(current_model_class))
