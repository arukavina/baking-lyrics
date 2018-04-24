#!/usr/bin/env python
"""
Flask End-Point
"""

# Generic
import os
import datetime
import configparser
import json

# Libs
from flask import Flask
from flask import abort
from flask import jsonify
from flask import request
from werkzeug.exceptions import HTTPException

# Own
from util import log_utils
from model.band import Band
from helpers import http_handler as http

app = Flask(__name__)
config_parser = configparser.ConfigParser()
bands = []

_valid_models = {
    'current': 'CurrentModel',
    'lstm': 'LSTMModel',
    'ngrams': 'NGramsModel'
}


@app.before_first_request
def load_bands():
    """Loads available bands in json file on memory"""
    try:
        config_parser.read("./CONFIG.INI")
        json_data = open(config_parser.get("PATHS", "BandsPath")).read()
        data = json.loads(json_data)
        for value in data["bands"]:
            band = Band()
            band.set_data(value)
            bands.append(band)
        logger.info("Bands loaded in memory")
    except FileNotFoundError as e:
        logger.error("Config file or bands file doesn't exist: " + str(e))
        abort(500, "Config file or bands file doesn't exist: " + str(e))
    except ValueError as e:
        logger.error("Json decoding for Bands file has failed: " + str(e))
        abort(500, "Json decoding for Bands file has failed: " + str(e))
    except Exception as e:
        logger.error("Unknown exception while parsing Bands file: " + str(e))
        abort(500, "Unknown exception while parsing Bands file: " + str(e))


@app.before_request
def before_request():
    values = '[{}] with {} - Request.Values: '.format(request.remote_addr, request.headers.get('User-Agent'))
    if len(request.values) == 0:
        values += '(None)'
    for key in request.values:
        values += '{}: {}, '.format(key, request.values[key])
    logger.info(values)


@app.route('/api/refresh_bands/', methods=['GET'])
def refresh_bands():
    """refresh list of bands in memory (the purpose of this is not have to reload api if json is updated)"""
    try:
        load_bands()
        return http.HttpHandler(200, "Success").return_json_http()
    except HTTPException:
        raise


@app.route('/api/bands', methods=['GET'])
def get_all_bands():
    """Return the list of all bands"""
    try:
        return jsonify(bands=[e.serialize() for e in bands])
    except HTTPException:
        raise


@app.route('/api/bands/<mask>', methods=['GET'])
def get_bands_by_mask(mask):
    """Returns the list of bands if the band name contains mask parameter"""
    try:
        mask_lower = mask.lower()
        return jsonify(bands=[e.serialize() for e in bands if e.name.lower().find(mask_lower) != -1])
    except HTTPException:
        raise


@app.route('/api/models/<model>/lyrics/<lang>/<length>/<words>/bands/<band>', methods=['GET'])
def get_lyrics_by_band(model, lang, length, words, band):
    """
    Returns a list of the list of <length> words in <lang> using the list of words <words>. Using Current model

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
            logger.error("Model not valid: {}".format(model))
            abort(400, "Model not valid: {}".format(model))

        model = _valid_models[model]

        if words is not None:
            words = str(words).split(' ')
        else:
            words = []

        _ModelClass, args = get_model_class(config_parser, model)

        model_instance = _ModelClass(**args)
        model_instance.__str__()

        logger.info("{} model initialized correctly".format(model))

        lyrics = ""

        try:
            lyrics = model_instance.generate_sentence(lang, length, 69, words, band)
        except NotImplementedError as e:
            logger.error("Not implemented error: " + str(e))
            abort(501, "Not implemented error: " + str(model))

        return jsonify(lyrics)
    except HTTPException:
        raise


@app.route('/api/models/<model>/lyrics/<lang>/<length>/<words>', methods=['GET'])
def get_lyrics(model, lang, length, words):
    """
    Returns a list of the list of <length> words in <lang> using the list of words <words>. Using Current model

    :param model: model to be used
    :param lang: language of model to use
    :param length: int, number of characters to generate
    :param words: list of words to use as a seed
    :return: string

    """
    try:
        lang = lang.lower()
        length = int(length)
        words = str(words).split(' ')
        model = str(model)

        if not validate_model(model):
            logger.error("Model not valid: {}".format(model))
            abort(400, "Model not valid: {}".format(model))

        model = _valid_models[model]

        if words is not None:
            words = str(words).split(' ')
        else:
            words = []

        _ModelClass, args = get_model_class(config_parser, model)

        model_instance = _ModelClass(**args)
        model_instance.__str__()

        logger.info("{} model initialized correctly".format(model))

        lyrics = ""

        try:
            lyrics = model_instance.generate_sentence(lang, length, 69, words)
        except NotImplementedError as e:
            logger.error("Not implemented error: " + str(e))
            abort(501, "Not implemented error: " + str(model))

        return jsonify(lyrics)
    except HTTPException:
        raise


@app.errorhandler(400)
def bad_request_error(error):
    error_object = http.HttpHandler(400, error)
    return error_object.return_json_http()


@app.errorhandler(404)
def not_found_error(error):
    error_object = http.HttpHandler(404, error)
    return error_object.return_json_http()


@app.errorhandler(500)
def internal_server_error(error):
    error_object = http.HttpHandler(500, error)
    return error_object.return_json_http()


@app.errorhandler(501)
def not_implemented_error(error):
    error_object = http.HttpHandler(501, error)
    return error_object.return_json_http()


@app.errorhandler(503)
def service_unavailable(error):
    error_object = http.HttpHandler(503, error)
    return error_object.return_json_http()


def validate_model(model_name):
    return model_name in _valid_models


def get_model_class(config, model):

    import importlib

    config.read("./CONFIG.INI")
    current_model_class = config.get("MODELS", model)

    if current_model_class == 'LSTMModel':

        args = dict(
            model_file_path=config.get("LSTMModel", "ModelFilePath"),
            weights_file_path=config.get("LSTMModel", "WeightsFilePath"),
            seed_file_path=config.get("LSTMModel", "SeedFilePath")
            )

        _ModelClass = getattr(importlib.import_module("ml.ml_abc"), current_model_class)
        return _ModelClass, args

    elif current_model_class == 'NGramsModel':

        # TODO: Read model args.
        logger.error("Not implemented model class: " + str(current_model_class))
        abort(501, "Not implemented model class: " + str(current_model_class))

    else:
        logger.error("Not implemented model class: " + str(current_model_class))
        abort(501, "Not implemented model class: " + str(current_model_class))


if __name__ == '__main__':

    global logger

    root_dir = os.getcwd()

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M_%S')

    settings = dict(
        log_dir=r'logs/',
        log_level=2
    )

    log_utils.setup_logging('bl-api', timestamp, settings)
    logger = log_utils.get_logger('bl-api')

    log_utils.print_imports_versions(logger)

    logger.info('Initializing Flask Deamon...')

    app.run(host='127.0.0.1', port=5002)
