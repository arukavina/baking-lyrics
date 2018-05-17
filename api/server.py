#!/usr/bin/env python

# Generic
import datetime
import random

# Libs
from flask import Flask, Blueprint
from flask import render_template

# Own
from api.util import log_utils
from api.v1.endpoints.artists import ns as bands_namespace
from api.v1.endpoints.genres import ns as genres_namespace
from api.v1.endpoints.songs import ns as lyrics_namespace
from api.v1.endpoints.titles import ns as titles_namespace
from api.database import db
from api.v1.restplus import api
from api.v1.restplus import limiter
# import api.v1.errors

app = Flask(__name__,
            instance_relative_config=True,
            static_folder="static/dist",
            template_folder="static")

# Configure

# Load the default configuration
app.config.from_object('config.default')

# Load the configuration from the instance folder
app.config.from_pyfile('config.py')

# Load the file specified by the APP_CONFIG_FILE environment variable
# Variables defined here will override those in the default configuration
app.config.from_envvar('APP_CONFIG_FILE')

# Setting up logger
time_stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M_%S')

log_utils.setup_logging('baking-api', time_stamp, app.config)
logger = log_utils.get_logger('baking-api')
log_utils.print_imports_versions(logger)

logger.info('Starting {} server at http://{}:5000/api/v1'.format(app.config['ENV'], app.config['SERVER_NAME']))


@app.route("/ping")
@limiter.exempt
def ping():
    return "pong"


@app.route("/")
@limiter.exempt
def index():
    return render_template("index.html")


@app.route("/hello")
def hello():
    return get_random_lyric()


def get_random_lyric():
    """

    :return:
    """
    greeting_list = ['Ciao', 'Hei', 'Salut', 'Hola', 'Hallo', 'Hej']
    return random.choice(greeting_list)


def main():

    limiter.init_app(app)

    blueprint = Blueprint('api', __name__, url_prefix='/api/v1')
    api.init_app(blueprint)

    api.add_namespace(bands_namespace)
    api.add_namespace(genres_namespace)
    api.add_namespace(lyrics_namespace)
    api.add_namespace(titles_namespace)

    app.register_blueprint(blueprint)

    db.init_app(app)
    app.app_context().push()

    print(app.url_map)

    app.run(debug=app.config['DEBUG'], use_reloader=False)


if __name__ == "__main__":
    main()
