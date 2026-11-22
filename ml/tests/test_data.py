import json

import pandas as pd
import pytest

from ml.data import (
    COLUMNS,
    LanguageFilter,
    PrepConfig,
    clean_lyrics,
    display_name,
    is_placeholder,
    normalise_genre,
    prepare,
    read_lyrics_csv,
    restore_lines,
    split_by_song,
    write_outputs,
)

VERSE = "You know I'm gonna cut right to the chase\nSome women were made but me myself\n"


def _song(n: int) -> str:
    return "\n".join(f"line {i} of the song number {n} goes on and on" for i in range(6))


def _frame(artists: dict[str, int]) -> pd.DataFrame:
    rows = []
    idx = 0
    for artist, count in artists.items():
        for n in range(count):
            rows.append({"index": idx, "song": f"song-{artist}-{n}", "year": 2000 + n % 10, "artist": artist,
                         "genre": "Rock" if n % 3 else "Not Available", "lyrics": _song(idx)})
            idx += 1
    return pd.DataFrame(rows, columns=COLUMNS)


def test_clean_keeps_line_breaks_and_drops_annotations():
    text = "[Chorus]\n  Hello   there\r\n\r\n\r\nChorus:\nGeneral <i>Kenobi</i> " + VERSE * 3
    out = clean_lyrics(text, min_words=5)
    assert out.startswith("Hello there\n\nGeneral Kenobi You know")
    assert "[" not in out and "Chorus" not in out and "\n\n\n" not in out


@pytest.mark.parametrize("text", [None, float("nan"), "", "   ", "(Instrumental)", "INSTRUMENTAL",
                                  "Tekst piosenki: brak", "We do not have the lyrics for this song yet"])
def test_clean_drops_empty_and_placeholders(text):
    assert clean_lyrics(text, min_words=1) is None


def test_clean_drops_too_short_too_long_and_non_latin():
    assert clean_lyrics("just a few words here", min_words=30) is None
    assert clean_lyrics("word " * 50, min_words=1, max_words=10) is None
    assert clean_lyrics(chr(0x4E00) * 40 + " a b c", min_words=1) is None


def test_placeholder_rule_ignores_long_real_lyrics():
    assert not is_placeholder(VERSE * 20 + "instrumental break")


def test_restore_lines_splits_on_capitals_but_keeps_names_and_i():
    flat = "Oh baby how you doing You know I'm gonna cut right to the chase If I was in L A tonight Take me home"
    assert restore_lines(flat).split("\n") == [
        "Oh baby how you doing",
        "You know I'm gonna cut right to the chase",
        "If I was in",
        "L A tonight",
        "Take me home",
    ]


def test_restore_lines_leaves_lowercase_text_alone():
    flat = "playin everything so easy it's like you seem so sure still your ways you dont see"
    assert restore_lines(flat) == flat


def test_flattened_lyrics_get_heuristic_lines_in_auto_mode():
    flat = "Cloud of black Cloud of black North west territories Wake up pressurized every day " * 3
    assert "\n" in clean_lyrics(flat, line_mode="auto", min_words=5)
    assert "\n" not in clean_lyrics(flat, line_mode="none", min_words=5)
    assert clean_lyrics(VERSE * 3, line_mode="auto", min_words=5).count("\n") == 5


def test_read_csv_drops_leading_unnamed_index(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text(",index,song,year,artist,genre,lyrics\n0,0,a-song,2009,an-artist,Pop,la la\n", encoding="utf-8")
    df = read_lyrics_csv(path)
    assert list(df.columns) == COLUMNS
    assert df.iloc[0]["song"] == "a-song"


def test_read_csv_rejects_wrong_schema(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_lyrics_csv(path)


def test_heuristic_language_filter():
    lang = LanguageFilter("heuristic")
    assert lang.is_english("I know you love me baby and the night is young")
    assert not lang.is_english("Ich weiss nicht was soll es bedeuten dass ich so traurig bin")
    assert LanguageFilter("none").is_english("nichts")


def test_helpers_match_refresh_database_rules():
    assert display_name("beyonce-knowles") == "Beyonce Knowles"
    assert normalise_genre("Not Available") == "Other"
    assert normalise_genre("Hip-Hop") == "Hip-Hop"


def _cfg(**kw) -> PrepConfig:
    base = dict(min_songs=5, max_artists=2, max_songs_per_artist=8, min_words=5, lang_detector="heuristic",
                val_frac=0.25, test_frac=0.25)
    base.update(kw)
    return PrepConfig(**base)


def test_prepare_filters_caps_dedupes_and_splits_by_song():
    raw = _frame({"big": 12, "mid": 6, "tiny": 2, "other": 5})
    raw = pd.concat([raw, raw.iloc[[0]].assign(index=999, song="dup")], ignore_index=True)  # duplicate lyrics
    df, meta = prepare(raw, _cfg(), log=lambda *_: None)
    assert sorted(meta["artists"]) == ["big", "mid"]  # top 2 by song count with >= 5 songs
    assert (df["artist"] == "big").sum() == 8 and (df["artist"] == "mid").sum() == 6
    assert df["index"].is_unique and 999 not in set(df["index"])
    assert set(df["split"]) == {"train", "val", "test"}
    for _, songs in df.groupby("artist"):
        assert (songs["split"] == "train").sum() >= 1
    assert meta["artists"]["big"]["display_name"] == "Big"
    assert meta["artists"]["big"]["genre"] == "Rock"  # "Other" (from Not Available) is not preferred
    assert set(df["artist_id"]) == {1, 2} and meta["unknown_artist_id"] == 0


def test_split_is_deterministic():
    df, _ = prepare(_frame({"big": 12, "mid": 9}), _cfg(), log=lambda *_: None)
    again = split_by_song(df, _cfg())
    assert list(again) == list(df["split"])
    other = split_by_song(df, _cfg(seed=99))
    assert list(other) != list(df["split"])


def test_explicit_artist_list():
    df, meta = prepare(_frame({"big": 12, "mid": 9}), _cfg(artists=["mid"]), log=lambda *_: None)
    assert list(meta["artists"]) == ["mid"]


def test_write_outputs_catalog_schema(tmp_path):
    pytest.importorskip("pyarrow")
    cfg = _cfg()
    df, meta = prepare(_frame({"big": 12, "mid": 9}), cfg, log=lambda *_: None)
    info = write_outputs(df, meta, tmp_path, cfg, source="unit")
    catalog = pd.read_csv(tmp_path / "catalog.csv")
    assert list(catalog.columns) == COLUMNS
    assert set(catalog["artist"]) == set(meta["artists"])
    assert "\n" in catalog.iloc[0]["lyrics"]
    assert json.loads((tmp_path / "artists.json").read_text(encoding="utf-8")) == meta
    assert len(info["data_sha256"]) == 64
    assert len(pd.read_parquet(tmp_path / "songs.parquet")) == len(df)
