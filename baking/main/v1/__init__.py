#!/usr/bin/env python

# Generics

# Libs
from flask import Blueprint

# Own
from baking.main.util import log_utils
from baking.main.v1.endpoints.artificial_songs import ns as artificial_songs_namespace
from baking.main.v1.endpoints.artificial_titles import ns as artificial_titles_namespace
from baking.main.v1.endpoints.artists import ns as bands_namespace
from baking.main.v1.endpoints.general import ns as general_namespace
from baking.main.v1.endpoints.genres import ns as genres_namespace
from baking.main.v1.endpoints.songs import ns as lyrics_namespace

logger = log_utils.get_logger('baking-api')


def init_app(app, api):

    logger.info("Importing Blueprints...")
    blueprint = Blueprint('api', __name__, url_prefix='/api/v1')
    api.init_app(blueprint)

    api.add_namespace(bands_namespace)
    api.add_namespace(genres_namespace)
    api.add_namespace(lyrics_namespace)
    api.add_namespace(artificial_titles_namespace)
    api.add_namespace(artificial_songs_namespace)
    api.add_namespace(general_namespace)

    app.register_blueprint(blueprint)

    return app
