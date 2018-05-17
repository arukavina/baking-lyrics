# Generic
from datetime import datetime

from api.database import db
from sqlalchemy.orm.exc import NoResultFound


def get_one_or_create(session,
                      model,
                      **kwargs):
    try:
        return session.query(model).filter_by(**kwargs).one(), True
    except NoResultFound:
        return model(**kwargs), False


class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    lyrics = db.Column(db.Text)
    pub_date = db.Column(db.DateTime)
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'))
    artist = db.relationship('Artist', backref=db.backref('song', lazy='dynamic'))

    def __init__(self, title, lyrics, artist, pub_date=None):
        self.title = title
        self.lyrics = lyrics
        self.artist = artist

        if pub_date is None:
            pub_date = datetime.utcnow()
        self.pub_date = pub_date

    def __repr__(self):
        return '<Song %r>' % self.title


class Artist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    pub_date = db.Column(db.DateTime)
    country = db.Column(db.String(80))
    genre_id = db.Column(db.Integer, db.ForeignKey('genre.id'))
    genre = db.relationship('Genre', backref=db.backref('artist', lazy='dynamic'))

    def __init__(self, name, country, genre, pub_date=None):
        self.name = name
        self.country = country

        if pub_date is None:
            pub_date = datetime.utcnow()
        self.pub_date = pub_date

        self.genre = genre

    def __repr__(self):
        return '<Artist %r>' % self.name


class Genre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Genre %r>' % self.name
