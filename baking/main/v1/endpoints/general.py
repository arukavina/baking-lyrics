# Generic
import logging
import random

from flask import current_app, render_template

# Libs
from flask_restx import Resource
from sqlalchemy import func, select
from sqlalchemy.exc import NoResultFound

# Own
from baking.main import api, db
from baking.main.database.models import ArtificialSong, Artist, Share, Song
from baking.main.v1.serializers import build_version, general_stats, song

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
    Totals in one query and the top artists in another (grouped, no per artist queries).
    :return: dict matching the general_stats model
    """
    artists, songs_generated, shares = db.session.execute(select(
        select(func.count(Artist.id)).scalar_subquery(),
        select(func.count(ArtificialSong.id)).scalar_subquery(),
        select(func.count(Share.id)).scalar_subquery(),
    )).one()

    name = func.coalesce(func.nullif(Artist.clean_name, ''), Artist.name)
    generated = func.count(ArtificialSong.id)
    top_artists = db.session.execute(
        select(Artist.id, name.label('name'), generated.label('songs_generated'))
        .join(ArtificialSong, ArtificialSong.base_artist_id == Artist.id)
        .group_by(Artist.id, Artist.clean_name, Artist.name)
        .order_by(generated.desc(), name, Artist.id)
        .limit(TOP_ARTISTS_LIMIT)
    ).all()

    return {
        'artists': artists,
        'songs_generated': songs_generated,
        'shares': shares,
        'top_artists': [row._asdict() for row in top_artists],
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
