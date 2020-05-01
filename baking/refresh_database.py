# Generic
import datetime
import pandas as pd
import logging

# Libs
from sqlalchemy.orm.exc import NoResultFound

# Own
from baking.main import db, create_app
from baking.main.database.models import Genre, Artist, Song, ArtificialSong, ArtificialTitle

import os

print(os.getenv('PYTHONPATH'))

app = create_app()  # Is using ENV Variable APP_CONFIG_FILE=config/development.py
logger = logging.getLogger('baking-api')

aws = app.config.get('AWS')
resource = app.config.get('DATA_FILE_PATH')

if aws:
    import baking.main.util.aws_utils as aws

    logger.debug("Loading {} file from AWS...".format(resource))
    song_data = aws.read_s3_csv_as_tmpfile(resource)

else:
    logger.debug("Loading {} file from disk...".format(resource))
    song_data = pd.read_csv(resource)

db.init_app(app)
app.app_context().push()
db.drop_all()
db.create_all()


def count():
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', -1)

    logger.info("Loading songs data to internal DB")

    s = song_data.groupby('artist')['song'].count().sort_values(ascending=False)
    print(s[:900])


def refresh():
    logger.info("Loading songs data to internal DB")

    new_songs = 0
    MAX_SONGS = 10  # By artist

    s = song_data.groupby('artist')['song'].count().sort_values(ascending=False)

    merged = pd.merge(left=song_data, right=s[:900], left_on='artist', right_on='artist')
    merged.columns = ['index', 'song', 'year', 'artist', 'genre', 'lyrics', 'count']

    total_rows = len(merged)

    prev_artist = ''
    song_counter = 0

    for i, song in merged.iterrows():

        if i % 10000 == 0:
            logger.info("p:{}|l:{} [{:.1f}%] / {}".format(i, new_songs, (new_songs+1)/(i+1) * 100, total_rows))
            # logger.info(
            #     'Current Song: \"{}\" by {} from {} - {}'.format(song_str, artist_str, str(song['year']), genre_str))

        if prev_artist != song['artist']:
            song_counter = 0

        if song_counter >= MAX_SONGS:
            logger.debug('Limit of songs by artist reached')
            continue

        if str(song['lyrics']).strip() == '':
            logger.debug('Song ({}):{} by {} is empty. Skipping'.format(i, song['song'], song['artist']))
            continue

        if song['lyrics'] is None:
            logger.debug('Song ({}):{} by {} is NA. Skipping'.format(i, song['song'], song['artist']))
            continue

        if str(song['lyrics']).strip().lower().find('tekst') > 0:
            logger.debug(
                'Song ({}):{} by {}, Text NA (Tekst niedostę). Skipping'.format(i, song['song'], song['artist']))
            continue

        if str(song['lyrics']).strip().lower() == 'instrumental':
            logger.debug('Song ({}):{} by {} is instrumental. Skipping'.format(i, song['song'], song['artist']))
            continue

        if len(str(song['lyrics']).strip().lower()) <= 30:
            logger.debug(
                'Song ({}):{} by {} lyrics are too short -> {}. Skipping'.format(i, song['song'], song['artist'],
                                                                                 song['lyrics']))
            continue

        artist_str = ''  # str(song['artist'])
        song_str = ''
        genre_str = ''

        try:
            artist_str = str(song['artist']).strip().replace('-', ' ').title()
            song_str = str(song['song']).strip().replace('-', ' ').title()
            genre_str = str(song['genre']).strip().replace('-', ' ').title()
        except:
            logger.debug(
                'Failed while parsing record ({}): {} | {} | {}'.format(i, song['artist'], song['song'], song['genre']))
            continue

        if len(artist_str) > 160:
            logger.debug('Artist name too long: {}. Skipping'.format(artist_str))
            continue
        if len(song_str) > 150:
            logger.debug('Song title too long: {}. Skipping'.format(song_str))
            continue
        if len(genre_str) > 90:
            logger.debug('Genre name too long: {}. Skipping'.format(genre_str))
            continue

        try:
            artist = Artist.query.filter(Artist.clean_name == artist_str).one()
        except NoResultFound:
            try:
                genre = Genre.query.filter(Genre.name == genre_str).one()
            except:
                genre = Genre(name=genre_str)

            artist = Artist(name=song['artist'],
                            clean_name=artist_str,
                            cover=False,
                            country="US",
                            formation_date=datetime.date(1986, 6, 28),
                            genre=genre)

        db.session.add(Song(title=song_str,
                            lyrics=song['lyrics'],
                            publication_date=datetime.date(int(song['year']), 1, 1),
                            artist=artist
                            )
                       )

        new_songs += 1
        song_counter += 1
        prev_artist = song['artist']

        db.session.commit()

    logger.info("p:{}|l:{} [{:.1f}%] / {}".format(total_rows, new_songs, (new_songs + 1) / (total_rows + 1) * 100, total_rows))

    db.session.commit()


def create_artificial():
    number_artificial_songs = 30

    logger.info("Creating {} pre-existing artificial songs for deployment and tests".format(number_artificial_songs))

    for i, song in song_data.iterrows():

        try:
            artist = Artist.query.filter(Artist.name == str(song['artist'])).one()
        except NoResultFound:
            artist = Artist(name=song['artist'],
                            country="US",
                            formation_date=datetime.date(1987, 12, 5),
                            genre=Genre(name=song['genre']))

        artificial_title = ArtificialTitle(
            title=song['song'],
            creation_date=datetime.datetime.utcnow()
        )

        artificial_song = ArtificialSong(
            artificial_title=artificial_title,
            lyrics=song['lyrics'],
            model="Dummy",
            base_artist=artist,
            creation_date=datetime.datetime.utcnow()
        )
        db.session.add(artificial_song)
        db.session.flush()

        logger.info("{}/{}".format(i, number_artificial_songs))

        if i >= number_artificial_songs:
            break

    db.session.flush()
    db.session.commit()


if __name__ == '__main__':
    refresh()
    #create_artificial()
    #count()
