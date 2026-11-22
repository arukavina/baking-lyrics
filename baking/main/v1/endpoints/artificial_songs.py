# Generic
import inspect
import logging
import random
import re
import time

# Libs
import numpy as np
from flask import current_app as app
from flask import request
from flask_restx import Resource, abort

# Own
from baking.main import api, ratelimit
from baking.main.repository import get_repository, schema
from baking.main.v1.models import machine_learning as ml
from baking.main.v1.serializers import SHARE_NETWORKS, artificial_song, share_request, share_result

logger = logging.getLogger('baking-api')

ns = api.namespace('artificial_songs', description='Operations related to artificially generated songs')


def abort_if_ml_unavailable():
    """
    Generation needs the Keras models loaded by create_app. Answers 503 when they are not available
    (TensorFlow not installed, model files missing, or ENV == 'testing').
    """
    if not app.extensions.get('ml_available', False):
        abort(503, 'ML models are not loaded')


def abort_if_rate_limited(route, limits):
    """
    Answers 429 when the client exhausted one of `limits` (e.g. "10 per minute;100 per day") on `route`.
    Disabled with RATELIMIT_ENABLED = False.
    """
    if not app.config.get('RATELIMIT_ENABLED', True):
        return
    table = get_repository().table(schema.RATELIMIT)
    if ratelimit.is_rate_limited(table, ratelimit.client_ip(request), route, ratelimit.parse_limits(limits)):
        abort(429, 'Too many shares from this address, try again later.')


def artist_and_sample_song(artist_id):
    """
    The artist and its first song. Answers 400 when the artist does not exist and 404 when it has no songs.
    """
    repository = get_repository()
    artist = repository.get_artist(artist_id)
    if artist is None:
        abort(400, f'Artist ID = {artist_id} does not exist.')

    song = repository.first_song_of_artist(artist_id)
    if song is None:
        abort(404, f'No songs data for Artist ID = {artist_id} does not exist.')
    return artist, song


def genre_name(artist):
    return artist['genre']['name'] if artist.get('genre') else None


def save_generated_song(sample_title, lyrics, artist):
    """
    Stores the generated song with its title (the sample song title marked as artificial) and bumps the
    generated song counters of the stats.
    """
    return get_repository().create_generated_song(title=sample_title + '(Artificial)',
                                                  lyrics=lyrics,
                                                  model=app.config['MODEL_NAME_STR'],
                                                  base_artist_id=artist['id'])


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

    logger.info(f"Execution time: [{time.time() - start_time:.2f}] seconds")

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
        return get_repository().list_generated_songs()


@ns.route('/<int:artificial_song_id>')
@ns.response(404, 'ArtificialSong not found.')
class ArtificialSongItem(Resource):

    @ns.marshal_with(artificial_song)
    def get(self, artificial_song_id):
        """
        Returns a existing generated song.
        """
        found = get_repository().get_generated_song(artificial_song_id)
        if found is None:
            abort(404, 'Lyric does not exist.')
        return found


@ns.route('/<int:artificial_song_id>/shares')
@ns.response(400, 'Missing or unknown network.')
@ns.response(404, 'ArtificialSong not found.')
@ns.response(429, 'Too many shares from this address, try again later.')
class ArtificialSongShares(Resource):
    # Shares feed a public KPI, so limit how fast one client can add them

    @ns.expect(share_request, validate=True)
    @ns.marshal_with(share_result, code=201)
    def post(self, artificial_song_id):
        """
        Records a share of a generated song on a social network and returns its total shares.
        """
        abort_if_rate_limited('shares', app.config['SHARE_RATE_LIMIT'])

        network = (api.payload.get('network') or '').strip().lower()
        if network not in SHARE_NETWORKS:
            abort(400, 'Unknown network. Expected one of: {}.'.format(', '.join(SHARE_NETWORKS)))

        shares = get_repository().add_share(artificial_song_id, network)
        if shares is None:
            abort(404, 'Lyric does not exist.')

        return {'artificial_song_id': artificial_song_id, 'network': network, 'shares': shares}, 201


@ns.route('/generate/<lang>/seed/<seed>/words/<int:number_words>/artist/<int:artist_id>/',
          endpoint='artificial_songs_artificial_song_item_2')
@ns.response(400, 'Artist Id not found.')
@ns.response(404, 'No Songs for Artist Id found.')
@ns.response(411, 'Seed can not be empty.')
@ns.response(500, 'Internal server error.')
@ns.response(501, 'Artificial Songs can only be generated in english.')
@ns.response(503, 'ML models are not loaded.')
class ArtificialSongSeedGenerator(Resource):

    @ns.marshal_with(artificial_song)
    def get(self, lang='en', seed='', number_words=0, artist_id=None):
        """
        Returns a generated song for the lang, seed and artist_id limited to number_words
        """
        logger.info(f'[{inspect.stack()[0][3]}] - (lang: {lang})::(number_words: {number_words})::(artist_id:{artist_id})')

        if lang != 'en':
            abort(501, 'Artificial Songs can only be generated in english')

        if seed == '':
            abort(411, 'Seed can not be empty')

        try:
            artist, song = artist_and_sample_song(artist_id)

            abort_if_ml_unavailable()

            title = list(map(ml.text_pre_process, [song['title']]))[0]

            input_texts = list(map(ml.text_pre_process, seed.split('\n')))

            lyrics = generate_song(input_texts, artist['name'], genre_name(artist), title, word_count=number_words)

            return save_generated_song(song['title'], lyrics, artist)
        except ValueError as e:
            abort(500, f"Internal Server Error: {e}")


@ns.route('/generate/<lang>/words/<int:number_words>/artist/<int:artist_id>/',
          endpoint='artificial_songs_artificial_song_item_3')
@ns.response(400, 'Artist Id not found.')
@ns.response(404, 'No Songs for Artist Id found.')
@ns.response(411, 'Seed can not be empty.')
@ns.response(500, 'Internal server error.')
@ns.response(501, 'Artificial Songs can only be generated in english.')
@ns.response(503, 'ML models are not loaded.')
class ArtificialSongGenerator(Resource):

    @ns.marshal_with(artificial_song)
    def get(self, lang='en', number_words=0, artist_id=None):
        """
        Returns a generated song for the lang and artist_id limited to number_words
        """
        logger.info(f'[{inspect.stack()[0][3]}] - (lang: {lang})::(number_words: {number_words})::(artist_id:{artist_id})')

        if lang != 'en':
            abort(501, 'Artificial Songs can only be generated in english')

        try:
            artist, song = artist_and_sample_song(artist_id)

            # A random fragment from a song of the artist
            lyrics = song['lyrics'] or ''
            random_cut = random.randint(min(30, len(lyrics)), len(lyrics))
            fragment = lyrics[:random_cut]

            abort_if_ml_unavailable()

            title = list(map(ml.text_pre_process, [song['title']]))[0]

            input_texts = list(map(ml.text_pre_process, fragment.split('\n')))

            lyrics = generate_song(input_texts, artist['name'], genre_name(artist), title, word_count=number_words)

            return save_generated_song(song['title'], lyrics, artist)
        except ValueError as e:
            abort(500, f"Internal Server Error: {e}")

