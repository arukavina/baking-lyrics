# Generic
from datetime import datetime

from api.database import db


class Lyric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    body = db.Column(db.Text)
    pub_date = db.Column(db.DateTime)
    band_id = db.Column(db.Integer, db.ForeignKey('band.id'))
    band = db.relationship('Band', backref=db.backref('lyric', lazy='dynamic'))

    def __init__(self, title, body, band, pub_date=None):
        self.title = title
        self.body = body
        self.band = band

        if pub_date is None:
            pub_date = datetime.utcnow()
        self.pub_date = pub_date

    def __repr__(self):
        return '<Lyric %r>' % self.title


class Band(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    pub_date = db.Column(db.DateTime)
    country = db.Column(db.String(80))
    genre_id = db.Column(db.Integer, db.ForeignKey('genre.id'))
    genre = db.relationship('Genre', backref=db.backref('bands', lazy='dynamic'))

    def __init__(self, name, country, genre, pub_date=None):
        self.name = name
        self.country = country

        if pub_date is None:
            pub_date = datetime.utcnow()
        self.pub_date = pub_date

        self.genre = genre

    def __repr__(self):
        return '<Band %r>' % self.name


class Genre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Genre %r>' % self.name
