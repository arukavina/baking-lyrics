from flask import Flask
from flask import abort
from werkzeug.exceptions import HTTPException
import configparser
from helpers import ErrorHandler as Eh
import json
from Model import Band

app = Flask(__name__)
Config = configparser.ConfigParser()


@app.before_first_request
def load_bands():
    Config.read("./CONFIG.INI")
    json_data = open(Config.get("PATHS", "BandsPath")).read()
    data = json.loads(json_data)
    bands = []
    for value in data["bands"]:
        band = Band.Band()
        band.set_data(value)
        bands.append(band)
    print("First band in the list: " + bands[0].name)
    #TODO: Manage exceptions on reading configuration and bands json


@app.route('/api/eg/<int:eg_id>', methods=['GET'])
def get_tasks(eg_id):
    print("Im in")
    try:
        if eg_id == 0:
            abort(404, "problem")
        return "get example: " + str(eg_id)
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
