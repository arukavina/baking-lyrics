#!/usr/bin/env python
"""
Flask End-Point
"""

# Generic
import json
import random

# Libs
from flask import abort
from flask import jsonify
from flask import request
from flask import render_template
from werkzeug.exceptions import HTTPException

# Own
from baking_api import app
from baking_api.models import Band
from baking_api.helpers import http_handler as http
from baking_api.util import log_utils

_valid_models = {
    'current': 'Current_Model',
    'lstm': 'LSTMModel',
    'ngrams': 'NGramsModel'
}

logger = app.logger


@app.before_first_request
def load_bands():
    """Loads available bands in json file on memory"""
    try:
        json_data = open(app.config["BANDS_PATH"]).read()
        data = json.loads(json_data)
        for value in data["bands"]:
            band = Band()
            band.set_data(value)
            app.bands.append(band)
        logger.info("Bands loaded in memory")
    except FileNotFoundError as e:
        abort(500, "Config file or bands file doesn't exist: " + str(e))
    except ValueError as e:
        abort(500, "Json decoding for Bands file has failed: " + str(e))
    except Exception as e:
        abort(500, "Unknown exception while parsing Bands file: " + str(e))


@app.before_first_request
def load_current_models():

    lyrics_model = app.config["CURRENT_MODEL_LYRICS"]
    title_model = app.config["CURRENT_MODEL_TITLE"]

    _ModelClass_lyrics, args_lyrics = get_model_class(lyrics_model)
    _ModelClass_title, args_title = get_model_class(lyrics_model)

    app.current_lyrics_model = _ModelClass_lyrics(**args_lyrics)
    app.current_title_model = _ModelClass_title(**args_title)

    app.current_lyrics_model.__str__()
    app.current_title_model.__str__()

    logger.info("{} lyrics_model initialized correctly!".format(lyrics_model))
    logger.info("{} title_model initialized correctly!".format(title_model))


@app.before_request
def before_request():
    values = '[{}] with {} - Request.Values: '.format(request.remote_addr,
                                                      request.headers.get('User-Agent'))
    if len(request.values) == 0:
        values += '(None)'
    for key in request.values:
        values += '{}: {}, '.format(key, request.values[key])
    logger.info(values)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/hello")
def hello():
    return get_hello()


@app.route('/baking_api/refresh_bands/', methods=['GET'])
def refresh_bands():
    """
    Refresh list of bands in memory
    This function is to not have to reload baking_api if json is updated.
    """
    try:
        load_bands()
        return http.HttpHandler(200, "Success").return_json_http()
    except HTTPException:
        raise


@app.route('/baking_api/bands', methods=['GET'])
def get_all_bands():
    """
    Return the list of all bands
    :return: json of bands
    """
    ""
    try:
        return jsonify(bands=[e.serialize() for e in app.bands])
    except HTTPException:
        raise


@app.route('/baking_api/bands/<mask>', methods=['GET'])
def get_bands_by_mask(mask):
    """Returns the list of bands if the band name contains mask parameter"""
    try:
        mask_lower = mask.lower()
        return jsonify(bands=[e.serialize() for e in app.bands if
                              e.name.lower().find(mask_lower) != -1])
    except HTTPException:
        raise


@app.route('/baking_api/models/<model>/lyrics/<lang>/<length>/<words>/bands/<band>', methods=['GET'])
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
    except HTTPException:
        raise


@app.route('/baking_api/models/<model>/lyrics/<lang>/<length>/<words>', methods=['GET'])
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
    try:
        lang = lang.lower()
        length = int(length)
        words = str(words)
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
            lyrics = model_instance.generate_sentence(lang, length, 69, words)
        except NotImplementedError:
            abort(501, "Not implemented error: " + str(model))

        return jsonify(lyrics)
    except HTTPException:
        raise


@app.errorhandler(400)
def bad_request_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(400, error)
    return error_object.return_json_http(), error_object.code


@app.errorhandler(404)
def not_found_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(404, error)
    return error_object.return_json_http(),error_object.code


@app.errorhandler(500)
def internal_server_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(500, error)
    return error_object.return_json_http(), error_object.code


@app.errorhandler(501)
def not_implemented_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(501, error)
    return error_object.return_json_http(), error_object.code




@app.errorhandler(503)
def service_unavailable(error):
    logger.error(str(error))
    error_object = http.HttpHandler(503, error)
    return error_object.return_json_http(), error_object.code


def validate_model(model_name):
    return model_name in _valid_models


def get_hello():
    greeting_list = ['Ciao', 'Hei', 'Salut', 'Hola', 'Hallo', 'Hej']
    return random.choice(greeting_list)


def get_model_class(model):

    import importlib

    current_model_class = app.config[str(model).upper()]

    if current_model_class == 'LyricsLSTMModel':

        args = dict(
            model_file_path=app.config["LYRICS_LSTM_MODEL_FILE_PATH"],
            weights_file_path=app.config["LYRICS_LSTM_LSTM_MODEL_WEIGHTS_FILE_PATH"],
            seed_file_path=app.config["LYRICS_LSTM_LSTM_MODEL_SEED_FILE_PATH"]
            )

        _ModelClass = getattr(importlib.import_module("baking_api.ml_models"), current_model_class)
        return _ModelClass, args

    elif current_model_class == 'TitleLSSTMMModel':

        args = dict(
            model_file_path=app.config["TITLE_LSTM_MODEL_FILE_PATH"],
            tokenizer_file_path=app.config["TITLE_LSTM_TOKENIZER_FILE_PATH"]
        )

        _ModelClass = getattr(importlib.import_module("baking_api.ml_models"), current_model_class)
        return _ModelClass, args

    elif current_model_class == 'NGramsModel':
        abort(501, "Not implemented model class: " + str(current_model_class))

    else:
        abort(501, "Not implemented model class: " + str(current_model_class))
