# Generic
import logging
import inspect
import random
import time
import datetime
import os
import re

# Libs
from sqlalchemy.orm.exc import NoResultFound
from flask import current_app as app
from flask_restplus import Resource
from flask_restplus import abort
import numpy as np

# Own
from baking.main import api, db
from baking.main.database.models import ArtificialSong, Artist, ArtificialTitle, Song
from baking.main.v1.serializers import artificial_song
from baking.main.v1.models import machine_learning as ml

logger = logging.getLogger('baking-api')

ns = api.namespace('artificial_songs', description='Operations related to artificially generated songs')


def generate_song(input_texts, artist, genre, title, word_count=None):
    start_time = time.time()

    logger.info('Generating Lyrics for (input_text: [{}...])::(artist: {})::(genre:{})::(title:{})::(word_count:{})'.format(
        ' '.join(input_texts)[0:15], artist, genre, title, word_count
    ))

    ai = ml.LyricsSkthModel()

    enc_vector_title = ml.encode_verse(title, tokenizer=ai.tokenizer.tokenizer,
                                       model_stv_encoder=ai.model_stv_encoder,
                                       max_verse_length=20)

    enc_vector_song_mean = np.mean([ml.encode_verse(x,
                                                    tokenizer=ai.tokenizer.tokenizer,
                                                    model_stv_encoder=ai.model_stv_encoder,
                                                    max_verse_length=20)
                                    for x in input_texts], axis=0)

    _artist_token = np.array(ai.tokenizer.artist_tokenizer[artist]).reshape((1, 1))
    _genre_token = np.array(ai.tokenizer.genre_tokenizer[genre]).reshape((1, 1))

    seq, rawl, score = ai.generate_sentence(enc_vector_title,
                                            enc_vector_song_mean,
                                            _artist_token,
                                            _genre_token,
                                            num_generated=1 * 2,
                                            max_length=128,
                                            temperature=0.7,
                                            depth_search_replace=5,
                                            width_search_replace=128,
                                            batch_size=128,
                                            random_seed=2806)

    lyrics = ml.clean_place_holders(''.join(rawl))

    logger.info("Execution time: [{0:.2f}] seconds".format(time.time() - start_time))

    if word_count is not None:
        re_list = [m.start() for m in re.finditer(r' ', lyrics)]
        if len(re_list) >= word_count:
            return lyrics[:re_list[word_count - 1]]
        else:
            return lyrics
    else:
        return lyrics


@ns.route('/')
class ArtificialSongCollection(Resource):

    @ns.marshal_list_with(artificial_song)
    def get(self):
        """
        Returns list of generated songs
        """
        songs = ArtificialSong.query.all()
        return songs


@ns.route('/<int:artificial_song_id>')
@ns.response(404, 'ArtificialSong not found.')
class ArtificialSongItem(Resource):

    @ns.marshal_with(artificial_song)
    def get(self, artificial_song_id):
        """
        Returns a existing generated song.
        """

        try:
            return ArtificialSong.query.filter(ArtificialSong.id == artificial_song_id).one()
        except NoResultFound:
            abort(404, 'Lyric does not exist.')


@ns.route('/generate/<lang>/seed/<seed>/words/<int:number_words>/artist/<int:artist_id>/')
@ns.response(400, 'Artist Id not found.')
@ns.response(404, 'No Songs for Artist Id found.')
@ns.response(411, 'Seed can not be empty.')
@ns.response(500, 'Internal server error.')
@ns.response(501, 'Artificial Songs can only be generated in english.')
class ArtificialSongItem(Resource):

    @ns.marshal_with(artificial_song)
    def get(self, lang='en', seed='', number_words=0, artist_id=None):
        """
        Returns a generated song for the lang, seed and artist_id limited to number_words
        """
        logger.info('[{}] - (lang: {})::(number_words: {})::(artist_id:{})'.format(
            inspect.stack()[0][3],
            lang,
            number_words,
            artist_id
        ))

        if lang != 'en':
            abort(501, 'Artificial Songs can only be generated in english')

        if seed == '':
            abort(411, 'Seed can not be empty')

        try:

            artist = None
            title = None

            try:
                artist = Artist.query.filter(Artist.id == artist_id).one()
            except NoResultFound:
                abort(400, 'Artist ID = {} does not exist.'.format(artist_id))

            # Getting a random sample from a random song
            try:
                song = Song.query.filter(Song.artist_id == artist_id)[0]
                title = song.title

            except NoResultFound:
                abort(404, 'No songs data for Artist ID = {} does not exist.'.format(artist_id))

            artificial_title = ArtificialTitle(
                title=title + '(Artificial)',
                creation_date=datetime.datetime.utcnow()
            )

            title = list(map(ml.text_pre_process, [title]))[0]

            input_texts = list(map(ml.text_pre_process, seed.split('\n')))

            lyrics = generate_song(input_texts, artist.name, artist.genre.name, title, word_count=number_words)

            artificial_song = ArtificialSong(
                artificial_title=artificial_title,
                lyrics=lyrics,
                model=app.config['MODEL_NAME_STR'],
                base_artist=artist,
                creation_date=datetime.datetime.utcnow()
            )

            db.session.add(artificial_song)
            db.session.flush()
            db.session.commit()

            return artificial_song
        except ValueError as e:
            abort(500, "Internal Server Error: {}".format(e))


@ns.route('/generate/<lang>/words/<int:number_words>/artist/<int:artist_id>/')
@ns.response(400, 'Artist Id not found.')
@ns.response(404, 'No Songs for Artist Id found.')
@ns.response(411, 'Seed can not be empty.')
@ns.response(500, 'Internal server error.')
@ns.response(501, 'Artificial Songs can only be generated in english.')
class ArtificialSongItem(Resource):

    @ns.marshal_with(artificial_song)
    def get(self, lang='en', number_words=0, artist_id=None):
        """
        Returns a generated song for the lang and artist_id limited to number_words
        """
        logger.info('[{}] - (lang: {})::(number_words: {})::(artist_id:{})'.format(
            inspect.stack()[0][3],
            lang,
            number_words,
            artist_id
        ))

        if lang != 'en':
            abort(501, 'Artificial Songs can only be generated in english')

        try:

            artist = None
            title = None
            fragment = ''

            try:
                artist = Artist.query.filter(Artist.id == artist_id).one()
            except NoResultFound:
                abort(400, 'Artist ID = {} does not exist.'.format(artist_id))

            # Getting a random sample from a random song
            try:
                song = Song.query.filter(Artist.id == artist_id)[0]
                title = song.title
                lyrics = song.lyrics
                random_cut = random.randint(30, len(lyrics))
                fragment = song.lyrics[:random_cut]

            except NoResultFound:
                abort(404, 'No songs data for Artist ID = {} does not exist.'.format(artist_id))

            artificial_title = ArtificialTitle(
                title=title + '(Artificial)',
                creation_date=datetime.datetime.utcnow()
            )

            title = list(map(ml.text_pre_process, [title]))[0]

            input_texts = list(map(ml.text_pre_process, fragment.split('\n')))

            lyrics = generate_song(input_texts, artist.name, artist.genre.name, title, word_count=number_words)

            artificial_song = ArtificialSong(
                artificial_title=artificial_title,
                lyrics=lyrics,
                model=app.config['MODEL_NAME_STR'],
                base_artist=artist,
                creation_date=datetime.datetime.utcnow()
            )

            db.session.add(artificial_song)
            db.session.flush()
            db.session.commit()

            return artificial_song
        except ValueError as e:
            abort(500, "Internal Server Error: {}".format(e))


def get_model_class(model):
    """

    :param model:
    :return:
    """

    import importlib

    current_model_class = app.config[str(model).upper()]

    if current_model_class == 'ArtificialSongsLSTMModel':

        args = dict(
            model_file_path=app.config["LYRICS_LSTM_MODEL_FILE_PATH"],
            weights_file_path=app.config["LYRICS_LSTM_WEIGHTS_FILE_PATH"],
            seed_file_path=app.config["LYRICS_LSTM_SEED_FILE_PATH"]
        )

        _ModelClass = getattr(importlib.import_module("api.ml_models"), current_model_class)
        return _ModelClass, args

    elif current_model_class == 'TitleLSTMModel':

        args = dict(
            model_file_path=app.config["TITLE_LSTM_MODEL_FILE_PATH"],
            tokenizer_file_path=app.config["TITLE_LSTM_TOKENIZER_FILE_PATH"]
        )

        _ModelClass = getattr(importlib.import_module("api.ml_models"), current_model_class)
        return _ModelClass, args

    elif current_model_class == 'NGramsModel':
        abort(501, "Not implemented models class: " + str(current_model_class))

    else:
        abort(501, "Not implemented models class: " + str(current_model_class))
