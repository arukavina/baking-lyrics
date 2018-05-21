# Generic
import datetime
import pandas as pd

# Libs
from flask import Flask, Blueprint
from flask import render_template
from sqlalchemy.orm.exc import NoResultFound

# Own
from api.database import db
from api.database.models import Genre, Artist, Song

DATA_FILE_PATH = r'./resources/songdata.csv'
song_data = pd.read_csv(DATA_FILE_PATH)

app = Flask(__name__,
            instance_relative_config=True,
            static_folder="static/dist",
            template_folder="static")

# Configure

# Load the default configuration
app.config.from_object('config.default')

# Load the configuration from the instance folder
app.config.from_pyfile('config.py')

db.init_app(app)
app.app_context().push()
db.drop_all()
db.create_all()

pop = Genre(name='Pop')

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
                        pub_date=datetime.date(2016, 12, 5),
                        artist=artist
                        )
                   )
    if i % 1000 == 0:
        print("{}/{}".format(i, len(song_data)))
        db.session.commit()

print("{}".format(len(song_data)))
db.session.commit()
