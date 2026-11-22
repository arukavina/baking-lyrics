"""
/api/v1/genres endpoints. Seed data: one genre (id 1, "Pop") with one artist.
"""

# Own
from baking.tests.conftest import add_artists


def test_genre_get(client):
    response = client.get('/api/v1/genres/1')

    assert response.status_code == 200
    assert response.json == {'id': 1, 'name': 'Pop'}


def test_genre_get_unknown_is_404(client):
    response = client.get('/api/v1/genres/999')

    assert response.status_code == 404
    assert response.json == {'message': 'Genre not found.'}


def test_genre_list_includes_artists(client):
    response = client.get('/api/v1/genres/')

    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]['name'] == 'Pop'
    assert response.json == [{
        'artists': [{'id': 1, 'name': 'beyonce-knowles', 'clean_name': 'Beyonce Knowles', 'cover': False,
                     'country': 'US', 'formation_date': '1986-06-28T00:00:00', 'genre': 'Pop'}],
        'id': 1,
        'name': 'Pop',
    }]


def test_genre_list_groups_artists_by_genre(app_repo, client):
    app_repo.save_catalog(genres=[{'id': 2, 'name': 'Rock'}])
    rock = add_artists(app_repo, 2, genre_id=2)

    response = client.get('/api/v1/genres/')

    assert [g['name'] for g in response.json] == ['Pop', 'Rock']
    assert [a['id'] for a in response.json[0]['artists']] == [1]
    assert [a['id'] for a in response.json[1]['artists']] == rock
    assert {a['genre'] for a in response.json[1]['artists']} == {'Rock'}


