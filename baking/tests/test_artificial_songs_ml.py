"""
Artificial song generation with the real Keras models (optional `ml` extra).

Skipped unless tf_keras / keras-self-attention are installed and the model files are present in
MODELS_PATH. Ready for the ML follow-up.
"""

# Libs
import pytest

pytest.importorskip('tf_keras')
pytest.importorskip('keras_self_attention')

MODEL_SUFFIXES = (
    '.artist_genre_tokenizer.npz',
    '.tokenizer.pickle',
    '.embmat.npz',
    '.model.generator_word.h5',
    '.model.generator_context.h5',
    '.model.verse_emb_context.h5',
    '.model.skipthought.h5',
)


@pytest.fixture
def ml_app(aws, make_app):
    """
    Development config (testing never loads the models) on mocked, seeded DynamoDB tables.
    """
    import config.development as dev
    from baking.main import resolve_path
    from baking.tests.conftest import seed

    model_dir = resolve_path(dev.MODELS_PATH)
    missing = [s for s in MODEL_SUFFIXES if not (model_dir / (dev.MODEL_NAME_STR + s)).is_file()]
    if missing:
        pytest.skip(f'Lyrics model files missing in {model_dir}: {missing}')

    app = make_app('config/development.py', DATA_FILE_PATH='baking/resources/lyrics_4_tests.csv')
    if not app.extensions['ml_available']:
        pytest.skip('ML models could not be loaded')

    seed(app)
    return app


@pytest.fixture
def ml_client(ml_app):
    return ml_app.test_client()


def test_artificial_song_with_seed_get(ml_client):
    response = ml_client.get('/api/v1/artificial_songs/generate/en/seed/1234/words/100/artist/1/')

    assert response.status_code == 200
    assert response.json['lyrics']


def test_artificial_song_no_seed_get(ml_client):
    response = ml_client.get('/api/v1/artificial_songs/generate/en/words/100/artist/1/')

    assert response.status_code == 200
    assert response.json['lyrics']


def test_all_artificial_songs_get(ml_client):
    assert ml_client.get('/api/v1/artificial_songs/').status_code == 200


def test_one_artificial_songs_get(ml_client):
    assert ml_client.get('/api/v1/artificial_songs/1').status_code == 200
