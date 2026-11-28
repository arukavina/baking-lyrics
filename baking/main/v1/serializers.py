from flask_restx import fields

from baking.main import api

artist = api.model('Artist', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of a artist'),
    'name': fields.String(required=True, description='Artist name'),
    'clean_name': fields.String(required=True, description='Clean artist name'),
    'cover': fields.Boolean(description='If Artist is allowed to be selected in front page'),
    'country': fields.String(required=True, description='Artist\'s origin country'),
    'formation_date': fields.DateTime,
    'genre': fields.String(attribute='genre.name'),
    'wiki_title': fields.String(description='English Wikipedia page of the artist, if known'),
    'image_url': fields.String(description='Picture of the artist from that page, if any'),
})

pagination = api.model('A page of results', {
    'page': fields.Integer(description='Number of this page of results'),
    'pages': fields.Integer(description='Total number of pages of results'),
    'per_page': fields.Integer(description='Number of items per page of results'),
    'total': fields.Integer(description='Total number of results'),
})

page_of_artists = api.inherit('Page of artists', pagination, {
    'items': fields.List(fields.Nested(artist))
})

genre = api.model('Genre', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of a genre'),
    'name': fields.String(required=True, description='Genre name'),
})

genres_with_artists = api.inherit('Genres with artists', genre, {
    'artists': fields.List(fields.Nested(artist))
})

song = api.model('Song', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of a song'),
    'title': fields.String(required=True, description='Song title'),
    'lyrics': fields.String(required=True, description='Song lyrics'),
    'publication_date': fields.DateTime,
    'artist': fields.List(fields.Nested(artist)),
})

page_of_songs = api.inherit('Page of songs', pagination, {
    'items': fields.List(fields.Nested(song))
})

artificial_title = api.model('ArtificialTitle', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of an artificial title'),
    'title': fields.String(required=True, description='Title value'),
    'creation_date': fields.DateTime,
})

page_of_artificial_titles = api.inherit('Page of artificial titles', pagination, {
    'items': fields.List(fields.Nested(artificial_title))
})

user = api.model('User', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of an user'),
    'name': fields.String(required=True, description='User name'),
    'email': fields.String(required=True, description='User email'),
    'auth_method': fields.String(required=True, description='Authentication method'),
    'member_since': fields.DateTime,
})

artificial_song = api.model('ArtificialSong', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of an artificial song'),
    'artificial_title': fields.Nested(artificial_title),
    'lyrics': fields.String(required=True, description='Artificial song lyrics'),
    'model': fields.String(required=True, description='Model used'),
    'creation_date': fields.DateTime,
    'user': fields.Nested(user),
    'base_artist': fields.Nested(artist),
})

page_of_artificial_songs = api.inherit('Page of artificial songs', pagination, {
    'items': fields.List(fields.Nested(artificial_song))
})

build_version = api.model('Build version', {
    'version': fields.String(description='Project version from pyproject.toml, null when unknown'),
    'commit': fields.String(description='Full git commit sha of the build, null when unknown'),
    'date': fields.String(description='ISO 8601 commit date of the build, null when unknown'),
})

SHARE_NETWORKS = ('facebook', 'twitter', 'whatsapp')

share_request = api.model('Share request', {
    'network': fields.String(required=True, example='facebook',
                             description='Network the song was shared to, one of {} (case-insensitive)'.format(
                                 ', '.join(SHARE_NETWORKS))),
})

share_result = api.model('Share result', {
    'artificial_song_id': fields.Integer(description='The shared artificial song'),
    'network': fields.String(description='Network the song was shared to, lowercase'),
    'shares': fields.Integer(description='Total number of shares of the artificial song'),
})

top_artist = api.model('Top artist', {
    'id': fields.Integer(description='The unique identifier of the artist'),
    'name': fields.String(description='Artist clean name, falls back to the raw name'),
    'songs_generated': fields.Integer(description='Number of songs generated in the style of the artist'),
})

general_stats = api.model('General stats', {
    'artists': fields.Integer(description='Number of artists'),
    'songs_generated': fields.Integer(description='Number of generated songs'),
    'shares': fields.Integer(description='Number of shares of generated songs'),
    'top_artists': fields.List(fields.Nested(top_artist),
                               description='Up to 3 artists with the most generated songs, ties broken by name'),
})


def song_view(record):
    """
    A song record ready for the `song` model, whose `artist` field has always been a list holding the
    song's artist.
    """
    return {**record, 'artist': [record['artist']] if record.get('artist') else []}
