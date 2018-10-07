from flask_restplus import fields

from api.v1 import api

artist = api.model('Artist', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of a artist'),
    'name': fields.String(required=True, description='Artist name'),
    'country': fields.String(required=True, description='Artist\'s origin country'),
    'formation_date': fields.DateTime,
    'genre': fields.String(attribute='genre.name'),
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

artificial_title = api.model('ArtificialTitle', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of an artificial title'),
    'title': fields.String(required=True, description='Title value'),
    'creation_date': fields.DateTime,
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
