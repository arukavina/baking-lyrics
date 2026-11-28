"""
(Re)loads the songs dataset into the DynamoDB catalog (genres, artists and songs).

Usage:
    python -m baking.refresh_database --data baking/resources/lyrics.csv [--prefix baking-lyrics-dev] [--artificial 30]

The CSV follows the Kaggle "380,000 lyrics from MetroLyrics" schema (columns song, year, artist, genre and
lyrics; an `index` column and extra columns are ignored), so the ML pipeline's catalog.csv works as well.
Defaults: --data from DATA_FILE_PATH (else baking/resources/lyrics.csv), --prefix from BAKING_TABLE_PREFIX,
--region from AWS_REGION / AWS_DEFAULT_REGION, --endpoint-url from DYNAMODB_ENDPOINT_URL.

Rules (unchanged from the SQL version): the `--max-artists` (default MAX_ARTISTS) artists with the most songs in the
dataset, at most
`max_songs` songs each, skipping empty, too short, instrumental and "tekst" placeholder lyrics.

Ids are stable across reseeds, whatever the CSV: they follow the natural key of each record, never the dataset
order. A genre keeps its id by name, an artist by its raw `name` slug (e.g. bee-gees) and a song by (artist
slug, title); only records the catalog does not hold yet get new ids, from the id sequences. Records the new
data no longer produces are deleted, except artists that generated songs were made for: they are retired (kept
for their generated songs and the stats, left out of the artist lists). Generated songs and shares are kept.

Cover (front page) artists: the `cover_artists` artists with the most songs in the dataset. Ties are broken by a
stable hash of the artist name: the prepared data caps songs per artist, so many artists tie, and breaking ties by
id (alphabetical) would only ever show artists starting with a digit or an A.

Programmatic usage (e.g. tests):
    refresh(repository, read_song_data(path))
"""

# Generic
import argparse
import datetime
import hashlib
import logging
import os
from collections import defaultdict

# Libs
import pandas as pd

# Own
from baking.main import resolve_path
from baking.main.repository import DynamoRepository, schema

logger = logging.getLogger('baking-api')

MAX_ARTISTS = 900
MAX_SONGS_PER_ARTIST = 10
COVER_ARTISTS = 16
COLUMNS = ['song', 'year', 'artist', 'genre', 'lyrics']

FORMATION_DATE = datetime.datetime(1986, 6, 28)
COUNTRY = 'US'


def read_song_data(path):
    """
    Reads a songs CSV (relative paths are resolved against the repository root).
    :param path: str or Path
    :return: pandas.DataFrame
    """
    path = resolve_path(path)
    logger.debug(f'Loading {path} file from disk...')
    return pd.read_csv(path)


def load_song_data(app):
    """
    Reads the songs CSV named by app.config['DATA_FILE_PATH']. With AWS=True the value is an S3 object key.
    :param app: Flask app
    :return: pandas.DataFrame
    """
    resource = app.config.get('DATA_FILE_PATH')

    if app.config.get('AWS'):
        import baking.main.util.aws_utils as aws_utils

        logger.debug(f'Loading {resource} file from AWS...')
        with app.app_context():
            return aws_utils.read_s3_csv_as_tmpfile(resource)

    return read_song_data(resource)


def _clean_text(value):
    return str(value).strip().replace('-', ' ').title()


def _valid_lyrics(song, i):
    """The stripped lyrics, or None when the song must be skipped."""
    if pd.isna(song['lyrics']):
        logger.debug('Song ({}):{} by {} is NA. Skipping'.format(i, song['song'], song['artist']))
        return None

    lyrics = str(song['lyrics']).strip()

    if lyrics == '':
        logger.debug('Song ({}):{} by {} is empty. Skipping'.format(i, song['song'], song['artist']))
        return None
    if lyrics.lower().find('tekst') > 0:
        logger.debug('Song ({}):{} by {}, Text NA (Tekst niedostę). Skipping'.format(i, song['song'], song['artist']))
        return None
    if lyrics.lower() == 'instrumental':
        logger.debug('Song ({}):{} by {} is instrumental. Skipping'.format(i, song['song'], song['artist']))
        return None
    if len(lyrics) <= 30:
        logger.debug('Song ({}):{} by {} lyrics are too short. Skipping'.format(i, song['song'], song['artist']))
        return None
    return lyrics


def _tie_breaker(name):
    """A stable, alphabet independent order for artists with the same song count."""
    return hashlib.sha256(name.encode('utf-8')).hexdigest()


def build_catalog(song_data, max_songs=MAX_SONGS_PER_ARTIST, max_artists=MAX_ARTISTS, cover_artists=COVER_ARTISTS):
    """
    Applies the cleaning rules and assigns ids.
    :param song_data: DataFrame with at least the columns song, year, artist, genre and lyrics
    :param max_songs: maximum number of songs loaded by artist
    :param max_artists: number of artists (the ones with most songs in the dataset) considered
    :param cover_artists: number of artists flagged as cover (front page) artists
    :return: (genres, artists, songs) lists of repository records
    """
    missing = [column for column in COLUMNS if column not in song_data.columns]
    if missing:
        raise ValueError(f'Missing columns in the songs data: {missing}')

    counts = song_data.groupby('artist')['song'].count().sort_values(ascending=False)
    top = counts[:max_artists]
    selected = song_data[song_data['artist'].isin(top.index)]

    genres, artists, songs = {}, {}, []
    dataset_count = {}  # artist id -> songs of the artist in the dataset
    loaded = {}  # raw artist -> loaded songs

    for i, song in enumerate(selected[COLUMNS].to_dict('records')):

        if loaded.get(song['artist'], 0) >= max_songs:
            logger.debug('Limit of songs by artist reached')
            continue

        lyrics = _valid_lyrics(song, i)
        if lyrics is None:
            continue

        try:
            artist_str = _clean_text(song['artist'])
            song_str = _clean_text(song['song'])
            genre_str = _clean_text(song['genre'])
            # songdata.csv songs have no year: keep them without a publication date
            publication_date = None if pd.isna(song['year']) else datetime.datetime(int(song['year']), 1, 1)
        except (TypeError, ValueError):
            logger.debug('Failed while parsing record ({}): {} | {} | {}'.format(i, song['artist'], song['song'],
                                                                                song['genre']))
            continue

        if len(artist_str) > 160 or len(song_str) > 150 or len(genre_str) > 90:
            logger.debug(f'Name too long: {artist_str} | {song_str} | {genre_str}. Skipping')
            continue

        artist = artists.get(artist_str)
        if artist is None:
            genre = genres.get(genre_str)
            if genre is None:
                genre = genres[genre_str] = {'id': len(genres) + 1, 'name': genre_str}
            artist = artists[artist_str] = {
                'id': len(artists) + 1,
                'name': str(song['artist']),
                'clean_name': artist_str,
                'cover': False,
                'country': COUNTRY,
                'formation_date': FORMATION_DATE,
                'genre_id': genre['id'],
            }
            dataset_count[artist['id']] = int(counts[song['artist']])

        songs.append({
            'id': len(songs) + 1,
            'title': song_str,
            'lyrics': song['lyrics'],
            'publication_date': publication_date,
            'artist_id': artist['id'],
        })
        loaded[song['artist']] = loaded.get(song['artist'], 0) + 1

    ranked = sorted(artists.values(), key=lambda a: (-dataset_count[a['id']], _tie_breaker(a['name'])))
    for artist in ranked[:cover_artists]:
        artist['cover'] = True

    return list(genres.values()), list(artists.values()), songs


def _song_key(artist_name, title):
    return artist_name, (title or '').strip().lower()


def assign_stable_ids(repository, genres, artists, songs):
    """
    Replaces the dataset order ids of build_catalog by the ids the catalog already uses for the same genre name,
    artist name and (artist name, song title); records the catalog does not hold get new ids from the sequences.
    Updates the records (and their genre_id / artist_id references) in place.
    :return: (genres, artists, songs)
    """
    keys = repository.catalog_keys()
    genre_ids = {genre['name']: genre['id'] for genre in keys['genres']}
    artist_ids = {artist['name']: artist['id'] for artist in keys['artists']}
    artist_names = {artist['id']: artist['name'] for artist in keys['artists']}
    song_ids = defaultdict(list)  # key -> existing ids, lowest first; each is reused at most once
    for song in sorted(keys['songs'], key=lambda s: s['id']):
        song_ids[_song_key(artist_names.get(song['artist_id']), song['title'])].append(song['id'])

    def reuse_or_allocate(records, sequence, existing_id):
        found = [existing_id(record) for record in records]
        fresh = iter(repository.next_ids(sequence, sum(1 for record_id in found if record_id is None)))
        return {id(record): record_id if record_id is not None else next(fresh)
                for record, record_id in zip(records, found, strict=True)}

    genre_map = reuse_or_allocate(genres, 'genre', lambda genre: genre_ids.get(genre['name']))
    new_genre_ids = {genre['id']: genre_map[id(genre)] for genre in genres}
    for genre in genres:
        genre['id'] = genre_map[id(genre)]

    artist_map = reuse_or_allocate(artists, 'artist', lambda artist: artist_ids.get(artist['name']))
    names = {artist['id']: artist['name'] for artist in artists}  # dataset order ids
    new_artist_ids = {artist['id']: artist_map[id(artist)] for artist in artists}
    for artist in artists:
        artist['id'] = artist_map[id(artist)]
        artist['genre_id'] = new_genre_ids.get(artist['genre_id'], artist['genre_id'])

    def existing_song(song):
        candidates = song_ids.get(_song_key(names.get(song['artist_id']), song['title']))
        return candidates.pop(0) if candidates else None

    song_map = reuse_or_allocate(songs, 'song', existing_song)
    for song in songs:
        song['id'] = song_map[id(song)]
        song['artist_id'] = new_artist_ids[song['artist_id']]

    return genres, artists, songs


def refresh(repository, song_data, max_songs=MAX_SONGS_PER_ARTIST, max_artists=MAX_ARTISTS,
            cover_artists=COVER_ARTISTS):
    """
    Writes the catalog built from `song_data` with stable ids (see assign_stable_ids) and deletes the catalog
    records it no longer contains (artists of generated songs are retired instead). The stats totals are the
    numbers of artists and songs written, not a read of the index right after the writes (eventually consistent).
    :param repository: Repository
    :param song_data: DataFrame (see build_catalog)
    :param max_songs: maximum number of songs loaded by artist
    :param max_artists: number of artists (the ones with most songs in the dataset) loaded
    :param cover_artists: number of cover artists
    :return: number of songs loaded
    """
    logger.info('Loading songs data to DynamoDB')
    genres, artists, songs = build_catalog(song_data, max_songs=max_songs, max_artists=max_artists,
                                           cover_artists=cover_artists)
    assign_stable_ids(repository, genres, artists, songs)
    totals = {'artists': len(artists), 'songs': len(songs)}
    repository.save_catalog(genres=genres, artists=artists, songs=songs, totals=totals)
    deleted = repository.prune_catalog(genre_ids=[g['id'] for g in genres], artist_ids=[a['id'] for a in artists],
                                       song_ids=[s['id'] for s in songs], totals=totals)
    logger.info(f'{len(genres)} genres, {len(artists)} artists and {len(songs)} songs loaded, '
                f'{deleted} stale records deleted')
    return len(songs)


def create_artificial(repository, song_data, number_artificial_songs=30):
    """
    Creates pre-existing generated songs (model "Dummy") from the first rows of `song_data`, for demos and tests.
    Their base artist is the catalog artist with the same raw name, if any.
    """
    logger.info(f'Creating {number_artificial_songs} pre-existing artificial songs for deployment and tests')
    artist_ids = {artist['name']: artist['id'] for artist in repository.list_artists()}

    for i, song in enumerate(song_data.to_dict('records')):
        if i >= number_artificial_songs:
            break
        repository.create_generated_song(title=song['song'], lyrics=song['lyrics'], model='Dummy',
                                         base_artist_id=artist_ids.get(str(song['artist'])))
        logger.info(f'{i + 1}/{number_artificial_songs}')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog='python -m baking.refresh_database',
                                     description='Loads the songs dataset into the DynamoDB catalog.')
    parser.add_argument('--data', default=os.environ.get('DATA_FILE_PATH') or 'baking/resources/lyrics.csv',
                        help='songs CSV (Kaggle lyrics schema), default: DATA_FILE_PATH or %(default)s')
    parser.add_argument('--prefix', default=os.environ.get('BAKING_TABLE_PREFIX') or schema.DEFAULT_PREFIX,
                        help='table name prefix (default: BAKING_TABLE_PREFIX or %(default)s)')
    parser.add_argument('--region', default=os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
                        or 'us-east-1', help='AWS region (default: %(default)s)')
    parser.add_argument('--endpoint-url', default=os.environ.get('DYNAMODB_ENDPOINT_URL') or None,
                        help='DynamoDB endpoint, e.g. a moto server or DynamoDB Local')
    parser.add_argument('--max-songs', type=int, default=MAX_SONGS_PER_ARTIST, help='songs per artist')
    parser.add_argument('--max-artists', type=int, default=MAX_ARTISTS,
                        help='artists loaded; match the --max-artists used by ml.data for its catalog.csv')
    parser.add_argument('--cover-artists', type=int, default=COVER_ARTISTS, help='number of cover artists')
    parser.add_argument('--artificial', type=int, default=0,
                        help='also create this many "Dummy" generated songs (demo data)')
    return parser.parse_args(argv)


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logger.setLevel(logging.INFO)
    args = parse_args(argv)
    repository = DynamoRepository(prefix=args.prefix, region=args.region, endpoint_url=args.endpoint_url,
                                  cache_seconds=0)
    song_data = read_song_data(args.data)
    loaded = refresh(repository, song_data, max_songs=args.max_songs, max_artists=args.max_artists,
                     cover_artists=args.cover_artists)
    if args.artificial:
        create_artificial(repository, song_data, args.artificial)
    print(f'{loaded} songs loaded into {args.prefix}-catalog ({args.region})')
    return loaded


if __name__ == '__main__':
    main()
