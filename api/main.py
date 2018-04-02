from flask import Flask
from flask import abort
from flask import jsonify
from werkzeug.exceptions import HTTPException
import configparser
from helpers import HttpHandler as http
import json
from Model import Band

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


@app.errorhandler(404)
def not_found(error):
    error_object = http.HttpHandler(404, error)
    return error_object.return_json_http()


@app.errorhandler(505)
def not_found(error):
    error_object = http.HttpHandler(505, error)
    return error_object.return_json_http()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5002)
