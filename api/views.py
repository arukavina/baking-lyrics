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

logger = logging.getLogger('baking-lyrics')

ns = api.namespace('', description='Base operations')

# Global Objects:

bands = []
current_lyrics_model = None
current_title_model = None
current_lyrics_model_name = None
current_title_model_name = None


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


@ns.route('/api/models/<models>/lyrics/<lang>/<length>/<words>/bands/<band>', methods=['GET'])
@limiter.limit("100/day;15/hour;2/minute")
def get_lyrics_by_band(model, lang, length, words, band):
    """
    Returns a list of the list of <length> words in <lang> using the list of words <words>.
    Using Current models

    :param model: models to be used
    :param lang: language of models to use
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

        logger.info("{} models initialized correctly".format(model))

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




def validate_model(model_name):
    """
    @deprecated... Please remove
    :param model_name:
    :return:
    """
    _valid_models = {
        'current': 'Current_Model',
        'lstm': 'LSTMModel',
        'ngrams': 'NGramsModel'
    }

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
        abort(501, "Not implemented models class: " + str(current_model_class))

    else:
        abort(501, "Not implemented models class: " + str(current_model_class))
