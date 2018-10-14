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

app = create_app(r'config/testing.py')
logger = logging.getLogger('baking-api')

song_data = pd.read_csv(app.config.get('DATA_FILE_PATH'))

db.init_app(app)
app.app_context().push()
db.drop_all()
db.create_all()

pop = Genre(name='Pop')


def refresh():

    logger.info("Loading songs data to internal DB")

    for i, song in song_data.iterrows():

        try:
            artist = Artist.query.filter(Artist.name == str(song['artist'])).one()
        except NoResultFound:
            artist = Artist(name=song['artist'],
                            country="US",
                            formation_date=datetime.date(1987, 12, 5),
                            genre=pop)

        db.session.add(Song(title=song['song'],
                            lyrics=song['text'],
                            publication_date=datetime.date(2016, 12, 5),
                            artist=artist
                            )
                       )
        if i % 1000 == 0:
            logger.info("{}/{}".format(i, len(song_data)))
            db.session.commit()
    logger.info("{}".format(len(song_data)))
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
                            genre=pop)

        artificial_title = ArtificialTitle(
            title=song['song'],
            creation_date=datetime.datetime.utcnow()
        )

        artificial_song = ArtificialSong(
            artificial_title=artificial_title,
            lyrics=song['text'],
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
    create_artificial()
