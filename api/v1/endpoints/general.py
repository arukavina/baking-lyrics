# Generic
import logging
import random

# Libs
from flask_restplus import Resource
from flask import render_template

# Own
from api.database.models import Song
from api.v1 import db
from api.v1 import api
from api.v1.serializers import song

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


def get_random_lyric():
    """
    Obtain some random song from the DB
    :return: Str, HTML Code
    """
    number_songs = db.session.query(Song.id).count()
    logger.info("Getting one random song from a pool {}".format(number_songs))
    random_song = Song.query.filter(Song.id == random.randint(1, number_songs)).one()
    return random_song
