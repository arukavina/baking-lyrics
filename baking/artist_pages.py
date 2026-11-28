"""
The Wikipedia page (and its picture) of every catalog artist, kept in a reviewed CSV so the site never has to guess.

The list lives in baking/resources/artist_pages.csv with the columns:

- artist: the artist slug, as in the catalog `name` (e.g. bee-gees)
- wiki_title: the English Wikipedia page of the artist, empty when none was found
- image_url: a thumbnail (640 px or the next size Wikimedia serves) of the page's main image, empty if none
- source: how the page was found: exact (the name or a "(band)", "(musician)"... variant), search (full text
  search), manual (set by hand, never overwritten) or none (nothing about music was found)

Building or extending the list (only the artists missing from it are looked up; --refresh redoes all but the manual
rows):
    python -m baking.artist_pages --catalog ml/data/processed/catalog.csv

To fix a wrong page, put the right title in `wiki_title`, set `source` to manual and clear `image_url`; the next run
fills the picture in. Seeding (baking.refresh_database) copies `wiki_title` and `image_url` into the catalog, and the
API serves them with each artist.

Same rules as the frontend fallback (baking-lyrics-web src/helpers/api/wikipedia.js): a page only counts when its
short description is about music, because many artist names are common words (Scorpions, Alabama, Queen).
"""

# Generic
import argparse
import csv
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# Libs
import pandas as pd

# Own
from baking.main import resolve_path

logger = logging.getLogger(__name__)

PAGES_FILE = 'baking/resources/artist_pages.csv'
FIELDS = ['artist', 'wiki_title', 'image_url', 'source']
EXACT, SEARCH, MANUAL, NONE = 'exact', 'search', 'manual', 'none'

WIKIPEDIA_API = 'https://en.wikipedia.org/w/api.php'
# Wikimedia asks automated clients for a descriptive user agent with a way to reach the operator
USER_AGENT = 'BakingLyrics/0.5 (https://github.com/arukavina/baking-lyrics)'
THUMBNAIL_WIDTH = 640
TITLE_SUFFIXES = ['', ' (band)', ' (musician)', ' (singer)', ' (rapper)', ' (group)']
MUSIC_DESCRIPTION = re.compile(
    r'\b(bands?|singers?|rappers?|musicians?|music|musical|groups?|duo|trio|songwriters?|composers?|vocalists?|'
    r'guitarists?|pianists?|dj|record producers?|entertainers?|orchestra|choir|ensemble|hip hop|rock|pop|country|'
    r'jazz|metal|punk|soul|r&b|reggae|blues|folk)\b',
    re.IGNORECASE,
)


def display_name(slug):
    """The name the site shows for an artist slug (same rule as the seeding's clean_name)."""
    return str(slug).strip().replace('-', ' ').title()


def image_url(page):
    """The page thumbnail URL without the utm_* tracking parameters Wikimedia appends."""
    source = ((page or {}).get('thumbnail') or {}).get('source', '')
    if not source:
        return ''
    parts = urllib.parse.urlsplit(source)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if not k.startswith('utm_')]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def is_music_page(page):
    return bool(page) and bool(MUSIC_DESCRIPTION.search(page.get('description') or ''))


class Wikipedia:
    """
    Minimal client of the MediaWiki query API: one request at a time, at most one every `delay` seconds, and
    waiting out 429 and 503 answers (Retry-After, else an increasing pause).
    """

    def __init__(self, delay=1.0, retries=5, opener=urllib.request.urlopen):
        self.delay = delay
        self.retries = retries
        self.opener = opener
        self._last = 0.0

    def query(self, **params):
        params = {
            'action': 'query', 'format': 'json', 'formatversion': '2', 'redirects': '1',
            'prop': 'pageimages|description', 'piprop': 'thumbnail', 'pithumbsize': str(THUMBNAIL_WIDTH), **params,
        }
        request = urllib.request.Request(f'{WIKIPEDIA_API}?{urllib.parse.urlencode(params)}',
                                         headers={'User-Agent': USER_AGENT})
        for attempt in range(1, self.retries + 1):
            wait = self._last + self.delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                with self.opener(request, timeout=30) as response:
                    return json.load(response).get('query', {})
            except urllib.error.HTTPError as error:
                if error.code not in (429, 503) or attempt == self.retries:
                    raise
                pause = float(error.headers.get('Retry-After') or 10 * attempt)
                logger.warning(f'Wikipedia answered {error.code}, waiting {pause:.0f} s')
                time.sleep(pause)
        return {}

    def by_titles(self, titles):
        """Pages of `titles` (after normalization and redirects) by requested title; missing ones are left out."""
        result = self.query(titles='|'.join(titles))
        renamed = {r['from']: r['to'] for r in result.get('normalized', []) + result.get('redirects', [])}
        pages = {p['title']: p for p in result.get('pages', []) if not p.get('missing') and not p.get('invalid')}
        found = {}
        for title in titles:
            current, seen = title, set()
            while current in renamed and current not in seen:
                seen.add(current)
                current = renamed[current]
            if current in pages:
                found[title] = pages[current]
        return found

    def search(self, text, limit=5):
        result = self.query(generator='search', gsrsearch=text, gsrlimit=str(limit))
        return sorted(result.get('pages', []), key=lambda page: page.get('index', 0))


def resolve(wikipedia, name):
    """
    The music page of an artist display name: the exact title or a disambiguated variant (TITLE_SUFFIXES order),
    else the best ranked music page of a full text search.
    :return: (wiki_title, image_url, source) with source exact, search or none
    """
    titles = [f'{name}{suffix}' for suffix in TITLE_SUFFIXES]
    pages = wikipedia.by_titles(titles)
    page = next((pages[t] for t in titles if is_music_page(pages.get(t))), None)
    source = EXACT
    if page is None:
        page = next((p for p in wikipedia.search(name) if is_music_page(p)), None)
        source = SEARCH
    if page is None:
        return '', '', NONE
    return page['title'], image_url(page), source


def image_of(wikipedia, title):
    """The thumbnail of a given page (used for manual rows)."""
    return image_url(wikipedia.by_titles([title]).get(title))


def load_pages(path=PAGES_FILE):
    """artist slug -> row dict; {} when the file does not exist."""
    path = resolve_path(path)
    if not path.exists():
        return {}
    with open(path, newline='', encoding='utf-8') as handle:
        return {row['artist']: {field: row.get(field) or '' for field in FIELDS} for row in csv.DictReader(handle)}


def save_pages(pages, path=PAGES_FILE):
    path = resolve_path(path)
    with open(path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        for slug in sorted(pages):
            writer.writerow({field: pages[slug].get(field) or '' for field in FIELDS})


def update_pages(pages, slugs, wikipedia, refresh=False, save=None, save_every=25):
    """
    Resolves the artists of `slugs` that `pages` does not hold yet (all but the manual rows with `refresh`), and
    fills the picture of manual rows that have a title but no image.
    :param save: optional callable(pages) called every `save_every` lookups and at the end, so a long run can resume
    :return: number of artists looked up
    """
    looked_up = 0
    for slug in slugs:
        row = pages.get(slug)
        if row and row['source'] == MANUAL:
            if row['wiki_title'] and not row['image_url']:
                row['image_url'] = image_of(wikipedia, row['wiki_title'])
                looked_up += 1
        elif row is None or refresh:
            title, image, source = resolve(wikipedia, display_name(slug))
            pages[slug] = {'artist': slug, 'wiki_title': title, 'image_url': image, 'source': source}
            logger.info(f'{slug}: {source} {title}')
            looked_up += 1
        else:
            continue
        if save and looked_up % save_every == 0:
            save(pages)
    if save:
        save(pages)
    return looked_up


def catalog_slugs(path):
    """Distinct artist slugs of a songs CSV (the prepared catalog.csv or any Kaggle schema file)."""
    return sorted(pd.read_csv(resolve_path(path), usecols=['artist'])['artist'].dropna().astype(str).unique())


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--catalog', required=True, help='songs CSV whose artists to resolve, e.g. catalog.csv')
    parser.add_argument('--pages', default=PAGES_FILE, help='the artist pages CSV to extend')
    parser.add_argument('--refresh', action='store_true', help='look up again every artist except manual rows')
    parser.add_argument('--delay', type=float, default=1.0, help='seconds between Wikipedia requests')
    parser.add_argument('--limit', type=int, default=None, help='only the first N artists (for a quick try)')
    return parser.parse_args(argv)


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    args = parse_args(argv)
    pages = load_pages(args.pages)
    slugs = catalog_slugs(args.catalog)[:args.limit]
    looked_up = update_pages(pages, slugs, Wikipedia(delay=args.delay), refresh=args.refresh,
                             save=lambda p: save_pages(p, args.pages))
    counts = pd.Series([pages[s]['source'] for s in slugs if s in pages]).value_counts().to_dict()
    print(f'{looked_up} artists looked up; {len(pages)} in {args.pages}; sources for this catalog: {counts}')
    return looked_up


if __name__ == '__main__':
    main()
