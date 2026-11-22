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
        """All artists ordered by id."""

    @abstractmethod
    def get_artist(self, artist_id):
        """The artist or None."""

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
    def save_catalog(self, genres=(), artists=(), songs=()):
        """
        Writes (creates or overwrites) catalog records, then refreshes the catalog totals and moves the id
        sequences past the highest id written.
        """

    @abstractmethod
    def prune_catalog(self, genre_ids, artist_ids, song_ids):
        """Deletes every catalog record whose id is not listed. Returns the number of deleted records."""

    @abstractmethod
    def next_id(self, sequence):
        """Next value of an id sequence: 'genre', 'artist', 'song', 'artificial_song' or 'artificial_title'."""

    # Generated songs and titles

    @abstractmethod
    def list_titles(self):
        """All generated titles ordered by id."""

    @abstractmethod
    def create_title(self, title, creation_date=None):
        """Stores a generated title and returns it."""

    @abstractmethod
    def list_generated_songs(self):
        """All generated songs ordered by id."""

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
