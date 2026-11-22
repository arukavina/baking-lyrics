# Generic
import logging
import random

from flask import current_app, render_template

# Libs
from flask_restx import Resource
from sqlalchemy.exc import NoResultFound

# Own
from baking.main import api, db
from baking.main.database.models import Song
from baking.main.v1.serializers import build_version, song

logger = logging.getLogger('baking-api')

ns = api.namespace('general', description='General API operations')


@ns.route('/')
class Index(Resource):

    def get(self):
        """
        Returns Index file for API
        """
        return render_template("index.html")


@ns.route('/random')
class Random(Resource):

    @api.marshal_with(song)
    def get(self):
        """
        Returns Random lyric for demo page.
        """
        return get_random_lyric()


@ns.route('/ping')
class Ping(Resource):

    @staticmethod
    def get():
        """
        Returns pong to ping.
        """
        return "pong!"

    @staticmethod
    def post():
        """
        Returns pong to ping.
        """
        return "pong!"


@ns.route('/version')
class Version(Resource):

    @api.marshal_with(build_version)
    def get(self):
        """
        Returns the API version and the commit (sha and ISO 8601 date) it was built from.
        """
        return {
            'version': current_app.config.get('BUILD_VERSION'),
            'commit': current_app.config.get('BUILD_COMMIT'),
            'date': current_app.config.get('BUILD_COMMIT_DATE'),
        }


def get_random_lyric():
    """
    Obtain some random song from the DB
    :return: Str, HTML Code
    """
    number_songs = db.session.query(Song.id).count()
    logger.info(f"Getting one random song from {number_songs} pool.")
    if number_songs == 0:
        raise NoResultFound('No songs in the database')
    return Song.query.order_by(Song.id).offset(random.randrange(number_songs)).limit(1).one()
