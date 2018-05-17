from flask_restplus import fields

from api.v1.restplus import api

band = api.model('Band', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of a band'),
    'name': fields.String(required=True, description='Band name'),
    'country': fields.String(required=True, description='Band\'s origin country'),
    'pub_date': fields.DateTime,
    'genre': fields.String(attribute='genre.name'),
})

pagination = api.model('A page of results', {
    'page': fields.Integer(description='Number of this page of results'),
    'pages': fields.Integer(description='Total number of pages of results'),
    'per_page': fields.Integer(description='Number of items per page of results'),
    'total': fields.Integer(description='Total number of results'),
})

page_of_bands = api.inherit('Page of bands', pagination, {
    'items': fields.List(fields.Nested(band))
})

genre = api.model('Genre', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of a genre'),
    'name': fields.String(required=True, description='Genre name'),
})

genres_with_bands = api.inherit('Genres with bands', genre, {
    'bands': fields.List(fields.Nested(band))
})

lyric = api.model('Lyric', {
    'id': fields.Integer(readOnly=True, description='The unique identifier of a lyric'),
    'title': fields.String(required=True, description='Lyric title'),
    'body': fields.String(required=True, description='Lyric body'),
    'pub_date': fields.DateTime,
    'band': fields.List(fields.Nested(band)),
})

title = api.model('Title', {
    'body': fields.String(required=True, description='Generated Title'),
    'lyric': fields.List(fields.Nested(lyric)),
})
