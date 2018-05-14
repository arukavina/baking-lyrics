# Own
from api.database import db
from api.database.models import Band, Genre, Lyric


def create_lyric(data):
    title = data.get('title')
    body = data.get('body')
    band_id = data.get('band_id')
    band = Band.query.filter(Band.id == band_id).one()
    band.country = data.get('country')

    post = Lyric(title, body, band)
    db.session.add(post)
    db.session.commit()


def create_band(data):
    name = data.get('name')
    country = data.get('country')
    genre_id = data.get('genre_id')
    category = Genre.query.filter(Genre.id == genre_id).one()

    post = Band(name, country, category)
    db.session.add(post)
    db.session.commit()


def update_band(band_id, data):
    band = Band.query.filter(Band.id == band_id).one()
    band.name = data.get('name')
    band.country = data.get('country')
    genre_id = data.get('genre_id')
    band.genre = Genre.query.filter(Genre.id == genre_id).one()

    db.session.add(band)
    db.session.commit()


def delete_band(band_id):
    post = Band.query.filter(Band.id == band_id).one()
    db.session.delete(post)
    db.session.commit()


def create_genre(data):
    name = data.get('name')
    genre_id = data.get('id')

    genre = Genre(name)
    if genre_id:
        genre.id = genre_id

    db.session.add(genre)
    db.session.commit()


def update_genre(genre_id, data):
    genre = Genre.query.filter(Genre.id == genre_id).one()
    genre.name = data.get('name')
    db.session.add(genre)
    db.session.commit()


def delete_genre(genre_id):
    genre = Genre.query.filter(Genre.id == genre_id).one()
    db.session.delete(genre)
    db.session.commit()
