"""
Artist pages list (baking.artist_pages): the Wikipedia lookup rules, the CSV and how seeding serves it.
"""

# Generic
import io
import json
import urllib.error

# Libs
import pandas as pd
import pytest

# Own
from baking import artist_pages
from baking.artist_pages import Wikipedia, load_pages, resolve, save_pages, update_pages
from baking.refresh_database import refresh

LYRICS = 'these are long enough lyrics for a song\nwith two lines'


def page(title, description, image=None):
    return {'title': title, 'description': description, **({'thumbnail': {'source': image}} if image else {})}


class FakeWikipedia(Wikipedia):
    """Answers `titles` lookups from `pages` (with optional redirects) and searches from `search`."""

    def __init__(self, pages=(), redirects=None, search=None):
        super().__init__(delay=0)
        self.pages = {p['title']: p for p in pages}
        self.redirects = redirects or {}
        self.results = search or {}
        self.calls = []

    def query(self, **params):
        self.calls.append(params)
        if params.get('generator') == 'search':
            return {'pages': [{**p, 'index': i + 1} for i, p in enumerate(self.results.get(params['gsrsearch'], []))]}
        titles = params['titles'].split('|')
        redirects = [{'from': t, 'to': self.redirects[t]} for t in titles if t in self.redirects]
        found = [self.pages.get(self.redirects.get(t, t), {'title': self.redirects.get(t, t), 'missing': True})
                 for t in titles]
        return {'redirects': redirects, 'pages': found}


# Lookup rules

def test_skips_a_page_not_about_music_for_the_band_page():
    wikipedia = FakeWikipedia(pages=[page('Scorpions', 'Order of arachnids', 'arachnid.jpg'),
                                     page('Scorpions (band)', 'German rock band', 'band.jpg')])

    assert resolve(wikipedia, 'Scorpions') == ('Scorpions (band)', 'band.jpg', 'exact')
    assert wikipedia.calls[0]['titles'].startswith('Scorpions|Scorpions (band)|Scorpions (musician)|')
    assert len(wikipedia.calls) == 1


def test_prefers_the_plain_title_and_follows_redirects():
    wikipedia = FakeWikipedia(redirects={'Hank Williams Jr': 'Hank Williams Jr.'},
                              pages=[page('Hank Williams Jr.', 'American singer-songwriter', 'hank.jpg')])

    assert resolve(wikipedia, 'Hank Williams Jr') == ('Hank Williams Jr.', 'hank.jpg', 'exact')


def test_falls_back_to_the_best_ranked_music_search_result():
    wikipedia = FakeWikipedia(search={'Ac Dc': [page('Direct current', 'Electric current'),
                                                page('AC/DC', 'Australian rock band', 'acdc.jpg')]})

    assert resolve(wikipedia, 'Ac Dc') == ('AC/DC', 'acdc.jpg', 'search')


def test_image_urls_lose_the_tracking_parameters():
    wikipedia = FakeWikipedia(pages=[page('Queen (band)', 'British rock band',
                                          'https://upload.wikimedia.org/q.jpg?utm_source=en.wikipedia.org&utm_campaign=api')])

    assert resolve(wikipedia, 'Queen')[1] == 'https://upload.wikimedia.org/q.jpg'


def test_a_variant_that_redirects_to_another_name_is_skipped():
    wikipedia = FakeWikipedia(redirects={'Prince (band)': 'The Revolution (band)'},
                              pages=[page('Prince', 'Royal title'),
                                     page('The Revolution (band)', 'American rock band', 'revolution.jpg'),
                                     page('Prince (musician)', 'American musician (1958 to 2016)', 'prince.jpg')])

    assert resolve(wikipedia, 'Prince') == ('Prince (musician)', 'prince.jpg', 'exact')


def test_search_hits_must_carry_the_artist_name():
    wikipedia = FakeWikipedia(search={'Bush': [page('Kate Bush', 'English singer-songwriter', 'kate.jpg')],
                                      'Cave Nick': [page('Nick Cave', 'Australian musician', 'nick.jpg')]})

    assert resolve(wikipedia, 'Bush') == ('', '', 'none')
    assert resolve(wikipedia, 'Cave Nick') == ('Nick Cave', 'nick.jpg', 'search')


@pytest.mark.parametrize('name, title, same', [
    ('Brooks Dunn', 'Brooks & Dunn', True),
    ('Echo The Bunnymen', 'Echo & the Bunnymen', True),
    ('Ac Dc', 'AC/DC', True),
    ('Gilbert Osullivan', "Gilbert O'Sullivan", True),
    ('Queen', 'Queen (band)', True),
    ('Anita O Day', "Anita O'Day", True),
    ('Andrew Wk', 'Andrew W.K.', True),
    ('The Go Go S', "The Go-Go's", True),
    ('Bush', 'Kate Bush', False),
    ('Prince', 'The Revolution (band)', False),
])
def test_same_name(name, title, same):
    assert artist_pages.same_name(name, title) is same


def test_recheck_only_looks_up_uncertain_rows():
    pages = {
        'queen': {'artist': 'queen', 'wiki_title': 'Queen (band)', 'image_url': 'q.jpg', 'source': 'exact'},
        'prince': {'artist': 'prince', 'wiki_title': 'The Revolution (band)', 'image_url': 'r.jpg', 'source': 'exact'},
        'bush': {'artist': 'bush', 'wiki_title': 'Kate Bush', 'image_url': 'k.jpg', 'source': 'search'},
    }
    wikipedia = FakeWikipedia(pages=[page('Prince (musician)', 'American musician', 'prince.jpg'),
                                     page('Bush (British band)', 'British rock band', 'bush.jpg')])

    looked_up = update_pages(pages, ['bush', 'prince', 'queen'], wikipedia, recheck=True)

    assert looked_up == 2
    assert pages['prince']['wiki_title'] == 'Prince (musician)'
    assert pages['bush']['wiki_title'] == 'Bush (British band)'
    assert pages['queen']['image_url'] == 'q.jpg'


def test_nothing_about_music_is_none():
    wikipedia = FakeWikipedia(pages=[page('Alabama', 'State of the United States', 'state.jpg')])

    assert resolve(wikipedia, 'Alabama') == ('', '', 'none')


def test_a_music_page_without_a_picture_keeps_its_title():
    wikipedia = FakeWikipedia(pages=[page('Eels (band)', 'American indie rock band')])

    assert resolve(wikipedia, 'Eels') == ('Eels (band)', '', 'exact')


# Client

class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_client_waits_out_rate_limits_and_sends_a_user_agent(monkeypatch):
    sleeps, requests = [], []
    monkeypatch.setattr(artist_pages.time, 'sleep', sleeps.append)

    def opener(request, timeout):
        requests.append(request)
        if len(requests) == 1:
            raise urllib.error.HTTPError(request.full_url, 429, 'Too Many Requests', {'Retry-After': '7'}, None)
        return Response(json.dumps({'query': {'pages': [page('Queen (band)', 'British rock band')]}}).encode())

    result = Wikipedia(delay=0, opener=opener).query(titles='Queen (band)')

    assert result['pages'][0]['title'] == 'Queen (band)'
    assert 7.0 in sleeps
    assert requests[0].get_header('User-agent') == artist_pages.USER_AGENT


def test_client_gives_up_on_other_errors(monkeypatch):
    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 400, 'Bad Request', {}, None)

    with pytest.raises(urllib.error.HTTPError):
        Wikipedia(delay=0, opener=opener).query(titles='x')


# The list

def test_only_missing_artists_are_looked_up_and_manual_rows_are_kept(tmp_path):
    path = tmp_path / 'pages.csv'
    save_pages({
        'queen': {'artist': 'queen', 'wiki_title': 'Queen (band)', 'image_url': 'q.jpg', 'source': 'exact'},
        'alabama': {'artist': 'alabama', 'wiki_title': 'Alabama (band)', 'image_url': '', 'source': 'manual'},
    }, path)
    wikipedia = FakeWikipedia(pages=[page('Alabama (band)', 'American country music band', 'alabama.jpg'),
                                     page('Eels (band)', 'American indie rock band', 'eels.jpg'),
                                     page('Queen (band)', 'British rock band', 'new-q.jpg')])
    pages = load_pages(path)

    looked_up = update_pages(pages, ['alabama', 'eels', 'queen'], wikipedia, save=lambda p: save_pages(p, path))

    assert looked_up == 2  # the manual row's missing picture and the new artist
    assert load_pages(path) == {
        'alabama': {'artist': 'alabama', 'wiki_title': 'Alabama (band)', 'image_url': 'alabama.jpg',
                    'source': 'manual'},
        'eels': {'artist': 'eels', 'wiki_title': 'Eels (band)', 'image_url': 'eels.jpg', 'source': 'exact'},
        'queen': {'artist': 'queen', 'wiki_title': 'Queen (band)', 'image_url': 'q.jpg', 'source': 'exact'},
    }


def test_refresh_looks_up_again_except_manual_rows():
    pages = {'queen': {'artist': 'queen', 'wiki_title': 'Queen', 'image_url': 'old.jpg', 'source': 'search'},
             'abba': {'artist': 'abba', 'wiki_title': 'ABBA', 'image_url': 'abba.jpg', 'source': 'manual'}}
    wikipedia = FakeWikipedia(pages=[page('Queen (band)', 'British rock band', 'q.jpg')])

    update_pages(pages, ['abba', 'queen'], wikipedia, refresh=True)

    assert pages['queen'] == {'artist': 'queen', 'wiki_title': 'Queen (band)', 'image_url': 'q.jpg',
                              'source': 'exact'}
    assert pages['abba']['image_url'] == 'abba.jpg'


def test_missing_file_is_an_empty_list(tmp_path):
    assert load_pages(tmp_path / 'nope.csv') == {}


# Seeding and the API

def test_seeding_serves_the_page_and_picture_of_each_artist(app_repo, client):
    data = pd.DataFrame([{'song': s, 'year': 2000, 'artist': a, 'genre': 'rock', 'lyrics': LYRICS}
                         for a, s in (('queen', 'one'), ('unknown-band', 'two'))])
    pages = {'queen': {'artist': 'queen', 'wiki_title': 'Queen (band)', 'image_url': 'q.jpg', 'source': 'exact'}}

    refresh(app_repo, data, pages=pages)
    ids = {a['name']: a['id'] for a in app_repo.list_artists()}
    queen = client.get(f"/api/v1/artists/{ids['queen']}").json
    unknown = client.get(f"/api/v1/artists/{ids['unknown-band']}").json

    assert (queen['wiki_title'], queen['image_url']) == ('Queen (band)', 'q.jpg')
    assert (unknown['wiki_title'], unknown['image_url']) == (None, None)
