# Own
from api.database import db
from api.database.models import Artist, Genre, Song


def create_song(data):
    title = data.get('title')
    lyrics = data.get('body')
    pub_date = data.get('pub_date')
    artist_id = data.get('artist_id')
    artist = Artist.query.filter(Artist.id == artist_id).one()
    artist.country = data.get('country')

    song = Song(title, lyrics, artist, pub_date)
    db.session.add(song)
    db.session.commit()


def update_song(song_id, data):
    song = Song.query.filter(Song.id == song_id).one()
    song.title = data.get('title')
    song.lyrics = data.get('lyrics')
    song.publication_date = data.get('publication_date')
    song.publication_date = data.get('publication_date')
    song.artist_id = data.get('artist_id')
    song.artist = Artist.query.filter(Artist.id == song.artist_id).one()

    db.session.add(song)
    db.session.commit()


def delete_song(song_id):
    post = Song.query.filter(Song.id == song_id).one()
    db.session.delete(post)
    db.session.commit()


def create_artist(data):
    name = data.get('name')
    country = data.get('country')
    pub_date = data.get('pub_date')
    genre_id = data.get('genre_id')
    genre = Genre.query.filter(Genre.id == genre_id).one()

    artist = Artist(name, country, genre, pub_date)
    db.session.add(artist)
    db.session.commit()


def update_artist(artist_id, data):
    artist = Artist.query.filter(Artist.id == artist_id).one()
    artist.name = data.get('name')
    artist.country = data.get('country')
    genre_id = data.get('genre_id')
    artist.genre = Genre.query.filter(Genre.id == genre_id).one()

    db.session.add(artist)
    db.session.commit()


def delete_artist(artist_id):
    post = Artist.query.filter(Artist.id == artist_id).one()
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
