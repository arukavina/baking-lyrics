"""
Artificial title generation with the real Keras title model (optional `ml` extra).

Skipped unless tf_keras is installed and the title model files are present. Ready for the ML
follow-up.
"""

# Libs
import pytest

pytest.importorskip('tf_keras')

TITLE_SUFFIXES = ('.h5', '.tokenizer.pickle')


@pytest.fixture
def ml_app(make_app):
    """
    Development config (testing never loads the models) on an isolated, seeded SQLite file.
    """
    from pathlib import Path

    import config.default as default
    from baking.main import db, resolve_path
    from baking.refresh_database import create_artificial, load_song_data, refresh

    base = resolve_path(default.TITLE_LSTM_MODEL_FILE_PATH)
    missing = [s for s in TITLE_SUFFIXES if not Path(str(base) + s).is_file()]
    if missing:
        pytest.skip(f'Title model files missing for {base}: {missing}')

    app = make_app('config/development.py', DATA_FILE_PATH='baking/resources/lyrics_4_tests.csv')
    if not app.extensions['ml_available']:
        pytest.skip('ML models could not be loaded')

    with app.app_context():
        db.create_all()
        song_data = load_song_data(app)
        refresh(app, song_data)
        create_artificial(song_data)

    return app


@pytest.fixture
def ml_client(ml_app):
    return ml_app.test_client()


def test_artificial_title_get(ml_client):
    response = ml_client.get('/api/v1/artificial_titles/generate/en/song/1/')

    assert response.status_code == 200
    assert response.json['title']


def test_all_artificial_titles_get(ml_client):
    assert ml_client.get('/api/v1/artificial_titles/').status_code == 200
