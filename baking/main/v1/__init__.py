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
    """

    :param app:
    :param api:
    :return:
    """

    logger.info("Importing Blueprints...")
    # A new blueprint per app: flask-restx blueprints can only be registered once, and create_app
    # may be called several times (tests).
    blueprint = Blueprint('api', __name__, url_prefix='/api/v1')
    # Forget the setup state of a blueprint registered by a previous create_app call, otherwise
    # flask-restx would add this app's swagger/doc rules to the previous app.
    api.blueprint = None
    api.blueprint_setup = None
    api.init_app(blueprint)

    # Namespaces created with api.namespace() are already attached to `api` (and their resources
    # recorded) at import time. Calling api.add_namespace() again would register every resource a
    # second time under a suffixed endpoint, so only add the ones that are missing.
    for namespace in (bands_namespace, genres_namespace, lyrics_namespace, artificial_titles_namespace,
                      artificial_songs_namespace, general_namespace):
        if namespace not in api.namespaces:
            api.add_namespace(namespace)

    app.register_blueprint(blueprint)
    logger.info("Blueprints registered")
    return app
