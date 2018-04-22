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
from werkzeug.exceptions import HTTPException
from helpers import HttpHandler as http
from Model import Band

# Own
from util import log_utils

app = Flask(__name__)
Config = configparser.ConfigParser()
bands = []


@app.before_first_request
def load_bands():
    """Loads available bands in json file on memory"""
    try:
        Config.read("./CONFIG.INI")
        json_data = open(Config.get("PATHS", "BandsPath")).read()
        data = json.loads(json_data)
        for value in data["bands"]:
            band = Band.Band()
            band.set_data(value)
            bands.append(band)
        print("Bands loaded in memory")
    except FileNotFoundError as e:
        print("Config file or bands file doesn't exist: " + str(e))
        abort(505, "Config file or bands file doesn't exist: " + str(e))
    except ValueError as e:
        print("Json decoding for Bands file has failed: " + str(e))
        abort(505, "Json decoding for Bands file has failed: " + str(e))
    except Exception as e:
        print("Unknown exception while parsing Bands file: " + str(e))
        abort(505, "Unknown exception while parsing Bands file: " + str(e))


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


@app.route('/api/models/current/lyrics/<lang>/<length>/<words>', methods=['GET'])
def get_lyrics(lang, length, words):
    """
    Returns a list of the list of <length> words in <lang> using the list of words <seed>. Using Current model

    :param lang: langage of model to use
    :param length: int, number of characters to generate
    :param words: list of words to use as a seed
    :return: string

    """
    import importlib

    try:
        lang = lang.lower()
        length = int(length)
        words = str(words).split(' ')

        Config.read("./CONFIG.INI")
        current_model_class = Config.get("MODELS", "CurrentModel")

        if current_model_class == 'LSTMModel':
            model_file_path = Config.get("LSTMModel", "ModelFilePath")
            weights_file_path = Config.get("LSTMModel", "WeightsFilePath")
            seed_file_path = Config.get("LSTMModel", "SeedFilePath")

            _ModelClass = getattr(importlib.import_module("ml.mlAbc"), current_model_class)
            model = _ModelClass(model_file_path, weights_file_path, seed_file_path)
            model.__str__()

            logger.info("{} model initialized correctly".format(current_model_class))

        else:
            raise NotImplementedError

        lyrics = model.generate_sentence(lang, length, 69, words)

        return jsonify(lyrics)
    except HTTPException:
        raise


@app.errorhandler(404)
def not_found(error):
    error_object = http.HttpHandler(404, error)
    return error_object.return_json_http()


@app.errorhandler(505)
def not_found(error):
    error_object = http.HttpHandler(505, error)
    return error_object.return_json_http()


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
