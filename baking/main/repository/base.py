"""
Repository interface used by the endpoints, the seeding script and the stats.

Records are plain dicts shaped like the API serializers (see baking.main.v1.serializers):

- genre: ``{'id', 'name'}``
- artist: ``{'id', 'name', 'clean_name', 'cover', 'country', 'formation_date', 'genre_id', 'genre'}``
  where ``genre`` is a genre dict (or None) and ``formation_date`` a naive datetime (or None)
- song: ``{'id', 'title', 'lyrics', 'publication_date', 'artist_id', 'artist'}`` where ``artist`` is an
  artist dict (or None)
- title: ``{'id', 'title', 'creation_date'}``
- generated song: ``{'id', 'artificial_title', 'lyrics', 'model', 'creation_date', 'base_artist_id',
  'base_artist'}`` where ``artificial_title`` is a title dict and ``base_artist`` an artist dict (or None)

Ids are positive integers, as in the public URLs (/songs/5, /artificial_songs/12...).
"""

# Generic
from abc import ABC, abstractmethod


class Repository(ABC):

    # Catalog (genres, artists, songs): read only for the API

    @abstractmethod
    def list_genres(self):
        """All genres ordered by id."""

    @abstractmethod
    def get_genre(self, genre_id):
        """The genre or None."""

    @abstractmethod
    def list_artists(self):
        """All catalog artists ordered by id (retired artists are left out, see prune_catalog)."""

    @abstractmethod
    def get_artist(self, artist_id):
        """The artist, retired or not, or None."""

    @abstractmethod
    def search_artists(self, text):
        """Artists whose clean name contains `text` (case-insensitive), ordered by clean name then id."""

    @abstractmethod
    def cover_artists(self):
        """Artists flagged as cover (front page) artists, ordered by id."""

    @abstractmethod
    def list_songs(self):
        """All songs ordered by id."""

    @abstractmethod
    def page_songs(self, page, per_page):
        """
        One page of songs ordered by id: ``(songs, total)``. Reads only the songs up to the end of the page,
        never the whole catalog.
        """

    @abstractmethod
    def get_song(self, song_id):
        """The song or None."""

    @abstractmethod
    def first_song_of_artist(self, artist_id):
        """The song of the artist with the lowest id, or None."""

    @abstractmethod
    def random_song(self):
        """A random song, or None when there are no songs."""

    # Catalog writes (seeding and tests)

    @abstractmethod
    def catalog_keys(self):
        """
        The natural keys of every catalog record, retired artists included, for seeding with stable ids:
        ``{'genres': [{'id', 'name'}], 'artists': [{'id', 'name'}], 'songs': [{'id', 'title', 'artist_id'}]}``.
        """

    @abstractmethod
    def save_catalog(self, genres=(), artists=(), songs=(), totals=None):
        """
        Writes (creates or overwrites, which also brings a retired artist back) catalog records and moves the id
        sequences past the highest id written. `totals` (``{'artists', 'songs'}``) are the catalog totals of the
        stats; when None they are counted from the tables.
        """

    @abstractmethod
    def prune_catalog(self, genre_ids, artist_ids, song_ids, totals=None):
        """
        Deletes every catalog record whose id is not listed, except artists that generated songs were made for:
        those are retired instead (kept for get_artist, left out of the artist lists) so generated songs keep
        their base artist. Returns the number of deleted records. `totals` as in save_catalog.
        """

    @abstractmethod
    def next_id(self, sequence):
        """Next value of an id sequence: 'genre', 'artist', 'song', 'artificial_song' or 'artificial_title'."""

    @abstractmethod
    def next_ids(self, sequence, count):
        """The next `count` values of an id sequence (one atomic update), ascending."""

    # Generated songs and titles

    @abstractmethod
    def list_titles(self):
        """All generated titles ordered by id."""

    @abstractmethod
    def page_titles(self, page, per_page):
        """One page of generated titles, most recent (highest id) first: ``(titles, total)``."""

    @abstractmethod
    def create_title(self, title, creation_date=None):
        """Stores a generated title and returns it."""

    @abstractmethod
    def list_generated_songs(self):
        """All generated songs ordered by id."""

    @abstractmethod
    def page_generated_songs(self, page, per_page):
        """One page of generated songs, most recent (highest id) first: ``(songs, total)``."""

    @abstractmethod
    def get_generated_song(self, song_id):
        """The generated song or None."""

    @abstractmethod
    def create_generated_song(self, title, lyrics, model, base_artist_id, creation_date=None):
        """
        Stores a generated song and its title (also listed as a generated title), bumps the generated
        song counters and returns the generated song.
        """

    # Shares and stats

    @abstractmethod
    def add_share(self, artificial_song_id, network):
        """Records a share. Returns the total shares of the generated song, or None when it does not exist."""

    @abstractmethod
    def get_stats(self, top=3):
        """
        ``{'artists', 'songs_generated', 'shares', 'top_artists'}`` where top_artists holds up to `top`
        ``{'id', 'name', 'songs_generated'}`` dicts: most generated songs first, ties by name then id, name being
        the clean name or, when empty, the raw name.
        """
