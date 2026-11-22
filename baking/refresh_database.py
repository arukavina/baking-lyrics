"""
(Re)loads the songs dataset into the database.

Usage (drops and recreates every table of the configured database):
    APP_CONFIG_FILE=config/development.py python -m baking.refresh_database

Programmatic usage (e.g. tests), inside an app context and after db.create_all():
    refresh(app, load_song_data(app))
"""

# Generic
import datetime
import logging

# Libs
import pandas as pd
from sqlalchemy.exc import NoResultFound

# Own
from baking.main import create_app, db, resolve_path
from baking.main.database.models import ArtificialSong, ArtificialTitle, Artist, Genre, Song, utcnow

logger = logging.getLogger('baking-api')

MAX_ARTISTS = 900


def load_song_data(app):
    """
    Reads the songs CSV named by app.config['DATA_FILE_PATH'].
    Local paths are resolved against the repository root; with AWS=True the value is an S3 object key.
    :param app: Flask app
    :return: pandas.DataFrame
    """
    resource = app.config.get('DATA_FILE_PATH')

    if app.config.get('AWS'):
        import baking.main.util.aws_utils as aws_utils

        logger.debug(f"Loading {resource} file from AWS...")
        with app.app_context():
            return aws_utils.read_s3_csv_as_tmpfile(resource)

    path = resolve_path(resource)
    logger.debug(f"Loading {path} file from disk...")
    return pd.read_csv(path)


def count(song_data):
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)

    s = song_data.groupby('artist')['song'].count().sort_values(ascending=False)
    print(s[:MAX_ARTISTS])


def refresh(app, song_data, max_songs=10):
    """
    Loads up to `max_songs` songs per artist (top MAX_ARTISTS artists by number of songs) into the DB.
    Must run inside an app context; tables must already exist.
    :param app: Flask app (kept for symmetry with load_song_data and future config lookups)
    :param song_data: DataFrame with columns index, song, year, artist, genre, lyrics
    :param max_songs: maximum number of songs loaded by artist
    :return: number of songs added
    """
    logger.info("Loading songs data to internal DB")

    new_songs = 0

    s = song_data.groupby('artist')['song'].count().sort_values(ascending=False)

    merged = pd.merge(left=song_data, right=s[:MAX_ARTISTS], left_on='artist', right_on='artist')
    merged.columns = ['index', 'song', 'year', 'artist', 'genre', 'lyrics', 'count']

    total_rows = len(merged)

    prev_artist = ''
    song_counter = 0

    for i, song in enumerate(merged.to_dict('records')):

        if i % 10000 == 0:
            logger.info(f"p:{i}|l:{new_songs} [{(new_songs+1)/(i+1) * 100:.1f}%] / {total_rows}")

        if prev_artist != song['artist']:
            song_counter = 0

        if song_counter >= max_songs:
            logger.debug('Limit of songs by artist reached')
            continue

        if pd.isna(song['lyrics']):
            logger.debug('Song ({}):{} by {} is NA. Skipping'.format(i, song['song'], song['artist']))
            continue

        lyrics = str(song['lyrics']).strip()

        if lyrics == '':
            logger.debug('Song ({}):{} by {} is empty. Skipping'.format(i, song['song'], song['artist']))
            continue

        if lyrics.lower().find('tekst') > 0:
            logger.debug(
                'Song ({}):{} by {}, Text NA (Tekst niedostę). Skipping'.format(i, song['song'], song['artist']))
            continue

        if lyrics.lower() == 'instrumental':
            logger.debug('Song ({}):{} by {} is instrumental. Skipping'.format(i, song['song'], song['artist']))
            continue

        if len(lyrics) <= 30:
            logger.debug(
                'Song ({}):{} by {} lyrics are too short -> {}. Skipping'.format(i, song['song'], song['artist'],
                                                                                 song['lyrics']))
            continue

        try:
            artist_str = str(song['artist']).strip().replace('-', ' ').title()
            song_str = str(song['song']).strip().replace('-', ' ').title()
            genre_str = str(song['genre']).strip().replace('-', ' ').title()
            year = int(song['year'])
        except (TypeError, ValueError):
            logger.debug(
                'Failed while parsing record ({}): {} | {} | {}'.format(i, song['artist'], song['song'], song['genre']))
            continue

        if len(artist_str) > 160:
            logger.debug(f'Artist name too long: {artist_str}. Skipping')
            continue
        if len(song_str) > 150:
            logger.debug(f'Song title too long: {song_str}. Skipping')
            continue
        if len(genre_str) > 90:
            logger.debug(f'Genre name too long: {genre_str}. Skipping')
            continue

        try:
            artist = Artist.query.filter(Artist.clean_name == artist_str).one()
        except NoResultFound:
            genre = Genre.query.filter(Genre.name == genre_str).first()
            if genre is None:
                genre = Genre(name=genre_str)

            artist = Artist(name=song['artist'],
                            clean_name=artist_str,
                            cover=False,
                            country="US",
                            formation_date=datetime.date(1986, 6, 28),
                            genre=genre)

        db.session.add(Song(title=song_str,
                            lyrics=song['lyrics'],
                            publication_date=datetime.date(year, 1, 1),
                            artist=artist
                            )
                       )

        new_songs += 1
        song_counter += 1
        prev_artist = song['artist']

        db.session.commit()

    logger.info(f"p:{total_rows}|l:{new_songs} [{(new_songs + 1) / (total_rows + 1) * 100:.1f}%] / {total_rows}")

    db.session.commit()
    return new_songs


def create_artificial(song_data, number_artificial_songs=30):
    """
    Creates pre-existing artificial songs for deployment and tests. Must run inside an app context.
    """
    logger.info(f"Creating {number_artificial_songs} pre-existing artificial songs for deployment and tests")

    for i, song in enumerate(song_data.to_dict('records')):

        if i >= number_artificial_songs:
            break

        try:
            artist = Artist.query.filter(Artist.name == str(song['artist'])).one()
        except NoResultFound:
            artist = Artist(name=song['artist'],
                            clean_name=str(song['artist']).strip().replace('-', ' ').title(),
                            country="US",
                            formation_date=datetime.date(1987, 12, 5),
                            genre=Genre(name=song['genre']))

        artificial_title = ArtificialTitle(
            title=song['song'],
            creation_date=utcnow()
        )

        artificial_song = ArtificialSong(
            artificial_title=artificial_title,
            lyrics=song['lyrics'],
            model="Dummy",
            base_artist=artist,
            creation_date=utcnow()
        )
        db.session.add(artificial_song)
        db.session.flush()

        logger.info(f"{i + 1}/{number_artificial_songs}")

    db.session.commit()


def main():
    app = create_app()  # Uses the APP_CONFIG_FILE environment variable, e.g. config/development.py
    song_data = load_song_data(app)

    with app.app_context():
        db.drop_all()
        db.create_all()
        refresh(app, song_data)


if __name__ == '__main__':
    main()
