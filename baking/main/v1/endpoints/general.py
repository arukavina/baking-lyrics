# Generic
import logging

from flask import current_app, render_template

# Libs
from flask_restx import Resource, abort

# Own
from baking.main import api
from baking.main.repository import get_repository
from baking.main.v1.serializers import build_version, general_stats, song, song_view

logger = logging.getLogger('baking-api')

TOP_ARTISTS_LIMIT = 3

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


@ns.route('/stats')
class Stats(Resource):

    @api.marshal_with(general_stats)
    def get(self):
        """
        Returns artist, generated song and share counts, plus the top 3 artists by generated songs.
        """
        return get_stats()


def get_stats():
    """
    Totals from the counters table plus the top artists by generated songs (no scan of generated songs).
    :return: dict matching the general_stats model
    """
    return get_repository().get_stats(top=TOP_ARTISTS_LIMIT)


def get_random_lyric():
    """
    A random song of the catalog, 404 when the catalog is empty.
    :return: dict matching the song model
    """
    found = get_repository().random_song()
    if found is None:
        abort(404, 'A database result was required but none was found.')
    return song_view(found)
