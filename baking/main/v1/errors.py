# Libs
import logging

# Own
from baking.main.v1 import create_app
from baking.main.util import http_handler as http

app = create_app(None)

logger = logging.getLogger('baking-api')


@app.errorhandler(400)
def bad_request_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(400, error)
    return error_object.return_json_http(), error_object.code


@app.errorhandler(404)
def not_found_error(error):
    logger.error(str(error))
    error_object = http.HttpHandler(404, error)
    return error_object.return_json_http(), error_object.code


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
