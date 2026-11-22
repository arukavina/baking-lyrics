# Generic
import inspect
import logging
import time

# Libs
from flask import current_app as app
from flask import request
from flask_restx import Resource, abort

# Own
from baking.main import api, ratelimit
from baking.main.repository import get_repository, schema
from baking.main.v1.models import generator
from baking.main.v1.serializers import SHARE_NETWORKS, artificial_song, share_request, share_result

logger = logging.getLogger('baking-api')

ns = api.namespace('artificial_songs', description='Operations related to artificially generated songs')


# Upper bound of the words generated per song (keeps a request well inside the Lambda timeout)
MAX_WORDS = 500


def model_service():
    """
    The lyrics model service. Answers 503 when generation is disabled (no MODEL_DIR / MODEL_BUCKET) or the
    model could not be loaded.
    """
    service = generator.get_service(app)
    if not service.settings.enabled:
        abort(503, 'ML models are not loaded')
    return service


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


def generate_song(artist, seed_text, number_words):
    """
    Generates lyrics and their title in the style of `artist` (catalog record; its `name` is the slug the model
    knows, unknown artists fall back to the generic style) continuing `seed_text`. Answers 503 when the model
    is not available. Returns (lyrics, title, model label).
    """
    service = model_service()
    number_words = max(1, min(int(number_words), MAX_WORDS))
    start_time = time.perf_counter()
    try:
        result, model = service.generate(artist=artist['name'], seed_text=seed_text, number_words=number_words)
    except generator.ModelUnavailable:
        result = None  # already logged by the service; abort outside the handler to keep the log short
    if result is None:
        abort(503, 'ML models are not loaded')
    logger.info('Generated %d words for artist %s (style %s) with %s in %.2f s', result.words, artist['name'],
                result.artist or 'generic', model.label, time.perf_counter() - start_time)
    return result.lyrics, result.title or 'Untitled', model.label


def save_generated_song(title, lyrics, model, artist):
    """Stores the generated song with its title and bumps the generated song counters of the stats."""
    return get_repository().create_generated_song(title=title, lyrics=lyrics, model=model, base_artist_id=artist['id'])


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
            artist, _ = artist_and_sample_song(artist_id)

            lyrics, title, model = generate_song(artist, seed, number_words)

            return save_generated_song(title, lyrics, model, artist)
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
            # The artist must have songs (404 otherwise); the model writes in its style without a prompt
            artist, _ = artist_and_sample_song(artist_id)

            lyrics, title, model = generate_song(artist, '', number_words)

            return save_generated_song(title, lyrics, model, artist)
        except ValueError as e:
            abort(500, f"Internal Server Error: {e}")
