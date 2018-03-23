from flask import Flask
from flask import abort
from flask import jsonify
from werkzeug.exceptions import HTTPException
import configparser
from helpers import ErrorHandler as Eh
import json
from Model import Band

app = Flask(__name__)
Config = configparser.ConfigParser()
bands = []


@app.before_first_request
def load_bands():
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


@app.route('/api/bands', methods=['GET'])
def get_all_bands():
    try:
        return jsonify(bands=[e.serialize() for e in bands])
    except HTTPException:
        raise


@app.errorhandler(404)
def not_found(error):
    error_object = Eh.ErrorHandler(404, error)
    return error_object.return_json_error()


@app.errorhandler(505)
def not_found(error):
    error_object = Eh.ErrorHandler(505, error)
    return error_object.return_json_error()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
