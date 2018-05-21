from flask_restplus import fields

from api.v1.restplus import api

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

title = api.model('Title', {
    'body': fields.String(required=True, description='Generated Title'),
    'song': fields.List(fields.Nested(song)),
})
