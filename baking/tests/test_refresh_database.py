"""
Seeding (baking.refresh_database): cleaning rules, ids, cover artists and the CLI, on moto.
"""

# Libs
import pandas as pd
import pytest

# Own
from baking.refresh_database import build_catalog, create_artificial, main, read_song_data, refresh
from baking.tests.conftest import TABLE_PREFIX, TEST_DATA

LYRICS = 'these are long enough lyrics for a song\nwith two lines'


def rows(*songs):
    """DataFrame in the Kaggle schema from (song, year, artist, genre, lyrics) tuples."""
    return pd.DataFrame([{'index': i, 'song': s[0], 'year': s[1], 'artist': s[2], 'genre': s[3], 'lyrics': s[4]}
                         for i, s in enumerate(songs)])


def test_build_catalog_from_the_test_csv():
    genres, artists, songs = build_catalog(read_song_data(TEST_DATA), cover_artists=0)

    assert genres == [{'id': 1, 'name': 'Pop'}]
    assert [(a['id'], a['name'], a['clean_name'], a['cover']) for a in artists] == [
        (1, 'beyonce-knowles', 'Beyonce Knowles', False)]
    assert [s['id'] for s in songs] == [1, 2, 3, 4, 5, 6]
    assert songs[0]['title'] == 'Ego Remix'


def test_cleaning_rules():
    data = rows(
        ('ok', 2001, 'a-band', 'rock', LYRICS),
        ('empty', 2001, 'a-band', 'rock', '   '),
        ('missing', 2001, 'a-band', 'rock', None),
        ('short', 2001, 'a-band', 'rock', 'too short'),
        ('instrumental', 2001, 'a-band', 'rock', 'Instrumental'),
        ('placeholder', 2001, 'a-band', 'rock', 'Lyrics: Tekst niedostepny, sorry about that one'),
        ('bad year', 'unknown', 'a-band', 'rock', LYRICS),
    )

    genres, artists, songs = build_catalog(data)

    assert [s['title'] for s in songs] == ['Ok']
    assert genres == [{'id': 1, 'name': 'Rock'}]
    assert artists[0]['clean_name'] == 'A Band'


def test_max_songs_per_artist_and_max_artists():
    data = rows(*[(f'song {i}', 2000, 'big', 'pop', LYRICS) for i in range(5)],
                *[(f'other {i}', 2000, 'small', 'jazz', LYRICS) for i in range(2)],
                ('lonely', 2000, 'tiny', 'jazz', LYRICS))

    genres, artists, songs = build_catalog(data, max_songs=3, max_artists=2)

    assert [a['clean_name'] for a in artists] == ['Big', 'Small']
    assert [s['artist_id'] for s in songs] == [1, 1, 1, 2, 2]
    assert [g['name'] for g in genres] == ['Pop', 'Jazz']


def test_cover_artists_are_the_ones_with_most_songs_in_the_dataset():
    data = rows(('a', 2000, 'first', 'pop', LYRICS),
                *[(f'b {i}', 2000, 'second', 'pop', LYRICS) for i in range(3)],
                *[(f'c {i}', 2000, 'third', 'pop', LYRICS) for i in range(2)])

    _, artists, _ = build_catalog(data, max_songs=1, cover_artists=2)

    assert {a['clean_name']: a['cover'] for a in artists} == {'First': False, 'Second': True, 'Third': True}


def test_extra_columns_are_ignored_and_missing_ones_fail():
    data = rows(('ok', 2001, 'band', 'rock', LYRICS)).assign(language='en')

    assert len(build_catalog(data)[2]) == 1
    with pytest.raises(ValueError, match='lyrics'):
        build_catalog(data.drop(columns=['lyrics']))


def test_refresh_is_idempotent_and_prunes(repo):
    data = rows(('one', 2000, 'band', 'rock', LYRICS), ('two', 2000, 'band', 'rock', LYRICS),
                ('three', 2000, 'other', 'pop', LYRICS))

    assert refresh(repo, data) == 3
    assert refresh(repo, data) == 3
    assert [s['id'] for s in repo.list_songs()] == [1, 2, 3]

    assert refresh(repo, data.iloc[:2]) == 2

    assert [s['id'] for s in repo.list_songs()] == [1, 2]
    assert [a['clean_name'] for a in repo.list_artists()] == ['Band']
    assert [g['name'] for g in repo.list_genres()] == ['Rock']
    assert repo.get_stats()['artists'] == 1


def test_create_artificial(repo):
    data = read_song_data(TEST_DATA)
    refresh(repo, data)

    create_artificial(repo, data, number_artificial_songs=2)

    generated = repo.list_generated_songs()
    assert [(g['artificial_title']['title'], g['model'], g['base_artist_id']) for g in generated] == [
        ('ego-remix', 'Dummy', 1), ('then-tell-me', 'Dummy', 1)]


def test_cli(repo, capsys):
    loaded = main(['--data', TEST_DATA, '--prefix', TABLE_PREFIX, '--artificial', '2'])

    assert loaded == 6
    assert '6 songs loaded' in capsys.readouterr().out
    assert len(repo.list_songs()) == 6
    assert repo.get_artist(1)['cover'] is True  # the only artist is in the top 16
    assert repo.get_stats()['songs_generated'] == 2
