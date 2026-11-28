"""
/api/v1/artists endpoints.

Seed data: one artist (id 1, "beyonce-knowles" / "Beyonce Knowles", genre "Pop", formation date
1986-06-28, cover False) with 6 songs.
"""

# Libs
import pytest

# Own
from baking.tests.conftest import add_artists

# The JSON served before the move to DynamoDB, byte for byte
SEEDED_ARTIST = {'id': 1, 'name': 'beyonce-knowles', 'clean_name': 'Beyonce Knowles', 'cover': False,
                 'country': 'US', 'formation_date': '1986-06-28T00:00:00', 'genre': 'Pop',
                 'wiki_title': None, 'image_url': None}


def _add_artists(app_repo, count, cover, formation_date=None):
    """Adds `count` artists to genre 1 and returns their ids."""
    return add_artists(app_repo, count, cover=cover, formation_date=formation_date)


# Read

def test_artist_get(client):
    response = client.get('/api/v1/artists/1')

    assert response.status_code == 200
    assert response.json == SEEDED_ARTIST


def test_artist_get_unknown_is_404(client):
    response = client.get('/api/v1/artists/999')

    assert response.status_code == 404
    assert response.json == {'message': 'Artist not found.'}


def test_artist_get_all(client):
    response = client.get('/api/v1/artists/')

    assert response.status_code == 200
    assert response.json['total'] == 1
    assert response.json == {'items': [SEEDED_ARTIST], 'page': 1, 'pages': 1, 'per_page': 10, 'total': 1}


# Search

def test_artist_get_by_name(client):
    response = client.get('/api/v1/artists/search/beyonce')

    assert response.status_code == 200
    assert response.json == [SEEDED_ARTIST]


def test_artist_search_is_case_insensitive(client):
    response = client.get('/api/v1/artists/search/KNOWLES')

    assert response.status_code == 200
    assert len(response.json) == 1


def test_artist_search_too_short_is_400(client):
    assert client.get('/api/v1/artists/search/be').status_code == 400


def test_artist_search_no_match_is_404(client):
    assert client.get('/api/v1/artists/search/metallica').status_code == 404


# Pagination

def test_artists_paginate(app_repo, client):
    _add_artists(app_repo, 4, cover=False)  # 5 artists in total

    first = client.get('/api/v1/artists/?page=1&per_page=2')
    last = client.get('/api/v1/artists/?page=3&per_page=2')

    assert first.status_code == 200
    assert first.json['total'] == 5
    assert first.json['pages'] == 3
    assert first.json['per_page'] == 2
    assert first.json['page'] == 1
    assert len(first.json['items']) == 2
    assert last.status_code == 200
    assert len(last.json['items']) == 1


def test_artists_paginate_past_last_page_is_empty(client):
    response = client.get('/api/v1/artists/?page=50&per_page=10')

    assert response.status_code == 200
    assert response.json['items'] == []
    assert response.json['total'] == 1


def test_artists_paginate_rejects_unsupported_per_page(client):
    assert client.get('/api/v1/artists/?per_page=3').status_code == 400


# Random famous artists

@pytest.mark.parametrize('number', [0, 5, 21, 100])
def test_artist_random_out_of_bounds_is_400(client, number):
    assert client.get(f'/api/v1/artists/random/{number}').status_code == 400


def test_artist_random_without_cover_artists_is_404(client):
    # The seeded artist has cover=False.
    assert client.get('/api/v1/artists/random/6').status_code == 404


def test_artist_random_returns_only_cover_artists(app_repo, client):
    cover_ids = _add_artists(app_repo, 8, cover=True)
    _add_artists(app_repo, 3, cover=False)

    response = client.get('/api/v1/artists/random/6')

    assert response.status_code == 200
    assert len(response.json) == 6
    assert {a['id'] for a in response.json} <= set(cover_ids)
    assert all(a['cover'] for a in response.json)


@pytest.mark.parametrize('number', [6, 20])
def test_artist_random_caps_to_available_cover_artists(app_repo, client, number):
    _add_artists(app_repo, 3, cover=True)

    response = client.get(f'/api/v1/artists/random/{number}')

    assert response.status_code == 200
    assert len(response.json) == 3


# Archive

def test_artist_get_archive(client):
    # Original test: a day with no artist still answers 200.
    response = client.get('/api/v1/artists/archive/1987/12/05/')

    assert response.status_code == 200
    assert response.json['items'] == []
    assert response.json['total'] == 0


@pytest.mark.parametrize('path, expected_ids', [
    ('1986/', [1]),
    ('1986/06/', [1]),
    ('1986/06/28/', [1]),
    ('1986/06/27/', []),
    ('1986/06/29/', []),
    ('1986/07/', []),
    ('1985/', []),
    ('1987/', []),
])
def test_artist_archive_filters_by_period(client, path, expected_ids):
    response = client.get(f'/api/v1/artists/archive/{path}')

    assert response.status_code == 200
    assert [a['id'] for a in response.json['items']] == expected_ids


def test_artist_archive_december_upper_bound(app_repo, client):
    import datetime

    december_ids = _add_artists(app_repo, 1, cover=False, formation_date=datetime.datetime(2000, 12, 31, 23, 0))
    _add_artists(app_repo, 1, cover=False, formation_date=datetime.datetime(2001, 1, 1))

    response = client.get('/api/v1/artists/archive/2000/12/')

    assert response.status_code == 200
    assert [a['id'] for a in response.json['items']] == december_ids


def test_artist_archive_paginates(app_repo, client):
    import datetime

    _add_artists(app_repo, 3, cover=False, formation_date=datetime.datetime(1999, 5, 5))

    response = client.get('/api/v1/artists/archive/1999/?per_page=2&page=2')

    assert response.status_code == 200
    assert response.json['total'] == 3
    assert len(response.json['items']) == 1


@pytest.mark.parametrize('path', ['2000/13/', '2000/02/30/', '2000/01/32/'])
def test_artist_archive_invalid_date_is_400(client, path):
    assert client.get(f'/api/v1/artists/archive/{path}').status_code == 400


@pytest.mark.parametrize('path', ['2000/00/', '2000/01/00/'])
def test_artist_archive_zero_month_or_day_is_400(client, path):
    assert client.get(f'/api/v1/artists/archive/{path}').status_code == 400


def test_artist_random_non_numeric_is_client_error(client):
    assert client.get('/api/v1/artists/random/abc').status_code in (400, 404)
