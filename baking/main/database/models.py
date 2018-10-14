# Generic
from datetime import datetime

from baking.main import db, flask_bcrypt
from flask_login import UserMixin


class User(UserMixin, db.Model):
    """ User Model for storing user related details """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    social_id = db.Column(db.String(64), nullable=False, unique=True)
    nickname = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(64), nullable=True)
    registered_on = db.Column(db.DateTime, nullable=False)
    admin = db.Column(db.Boolean, nullable=False, default=False)
    auth_method = db.Column(db.String(50))
    member_since = db.Column(db.DateTime)
    password_hash = db.Column(db.String(255))

    @property
    def password(self):
        raise AttributeError('password: write-only field')

    @password.setter
    def password(self, password):
        self.password_hash = flask_bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return flask_bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return "<User '{}'>".format(self.username)


class Genre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Genre %r>' % self.name


class Artist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    formation_date = db.Column(db.DateTime)
    country = db.Column(db.String(80))
    genre_id = db.Column(db.Integer, db.ForeignKey(Genre.id))
    genre = db.relationship(Genre, backref=db.backref('artist', lazy='dynamic'))

    def __init__(self, name, country, genre, formation_date=None):
        self.name = name
        self.country = country

        if formation_date is None:
            formation_date = datetime.utcnow()
        self.formation_date = formation_date

        self.genre = genre

    def __repr__(self):
        return '<Artist %r>' % self.name


class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    lyrics = db.Column(db.Text)
    publication_date = db.Column(db.DateTime)
    artist_id = db.Column(db.Integer, db.ForeignKey(Artist.id))
    artist = db.relationship(Artist, backref=db.backref('song', lazy='dynamic'))

    def __init__(self, title, lyrics, artist, publication_date=None):
        self.title = title
        self.lyrics = lyrics
        self.artist = artist

        if publication_date is None:
            publication_date = datetime.utcnow()
        self.publication_date = publication_date

    def __repr__(self):
        return '<Song %r>' % self.title

    def as_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'lyrics': self.lyrics,
            'publication_date': self.publication_date,
            'artist': self.artist.name
        }

    def __str__(self):
        return str(self.as_dict())


class ArtificialTitle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    creation_date = db.Column(db.DateTime)

    def __init__(self, title, creation_date=None):
        self.title = title

        if creation_date is None:
            creation_date = datetime.utcnow()
        self.creation_date = creation_date

    def __repr__(self):
        return '<ArtificialTitle %r>' % self.title


class ArtificialSong(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    artificial_title_id = db.Column(db.Integer, db.ForeignKey(ArtificialTitle.id))
    artificial_title = db.relationship(ArtificialTitle, backref=db.backref('artificialSong', lazy='dynamic'))
    lyrics = db.Column(db.Text)
    model = db.Column(db.String(50))
    creation_date = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User, backref=db.backref('artificialSong', lazy='dynamic'))
    base_artist_id = db.Column(db.Integer, db.ForeignKey(Artist.id))
    base_artist = db.relationship(Artist, backref=db.backref('artificialSong', lazy='dynamic'))

    def __init__(self, artificial_title, lyrics, model, base_artist, creation_date=None):
        self.artificial_title = artificial_title
        self.lyrics = lyrics
        self.model = model
        self.base_artist = base_artist

        if creation_date is None:
            creation_date = datetime.utcnow()
        self.creation_date = creation_date

    def __repr__(self):
        return '<ArtificialSong named: %r>' % self.artificial_title.title