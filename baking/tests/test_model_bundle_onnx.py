"""
Generation endpoints with a real ONNX bundle, trained and exported on the fly by the ml package.

Needs the `train` dependency group (torch, onnx, onnxscript, pyarrow) and the `ml` extra (onnxruntime);
skipped otherwise. The tiny model (2 artists, a few seconds of CPU training) is built once per module.
The seeded API artist (beyonce-knowles) is not one of the model's artists: it gets the generic style.
"""

# Libs
import boto3
import pytest

pytest.importorskip('torch')
pytest.importorskip('onnx')
pytest.importorskip('onnxscript')
pytest.importorskip('onnxruntime')
pytest.importorskip('pyarrow')

# Own
from baking.tests.conftest import REGION, seed  # noqa: E402

SEED_SONG = '/api/v1/artificial_songs/generate/en/seed/{seed}/words/{words}/artist/{artist}/'
NO_SEED_SONG = '/api/v1/artificial_songs/generate/en/words/{words}/artist/{artist}/'
TITLE = '/api/v1/artificial_titles/generate/en/song/{song}/'


@pytest.fixture(scope='module')
def bundle(tmp_path_factory):
    from ml.data import PrepConfig, prepare, write_outputs
    from ml.export import export_bundle
    from ml.tests.conftest import _corpus
    from ml.train import build_config, train

    data = tmp_path_factory.mktemp('data')
    prep = PrepConfig(min_songs=5, min_words=5, lang_detector='none', val_frac=0.2, test_frac=0.2)
    df, meta = prepare(_corpus(), prep, log=lambda *_: None)
    write_outputs(df, meta, data, prep, source='unit')
    run = tmp_path_factory.mktemp('run')
    cfg = build_config('smoke', None, ['epochs=1', 'max_steps_per_epoch=8', 'batch_size=4', 'min_freq=1',
                                       'sample_words=10', 'model.hidden=24', 'model.emb_dim=16'])
    train(data, run, cfg, device_name='cpu', log=lambda *_: None)
    return export_bundle(run, tmp_path_factory.mktemp('bundles'), version='test-1', log=lambda *_: None)


def check_song(response, seed_text=''):
    assert response.status_code == 200, response.json
    song = response.json
    assert song['model'] == 'lyrics-lstm/test-1'
    assert song['lyrics'].strip()
    assert song['lyrics'].lower().startswith(seed_text)
    assert song['artificial_title']['title'].strip()
    assert song['base_artist']['name'] == 'beyonce-knowles'
    return song


def test_generate_from_a_local_bundle(aws, make_app, bundle):
    app = make_app(MODEL_DIR=str(bundle))
    repository = seed(app)
    client = app.test_client()

    seeded = check_song(client.get(SEED_SONG.format(seed='night fever', words=12, artist=1)), 'night fever')
    free = check_song(client.get(NO_SEED_SONG.format(words=12, artist=1)))
    title = client.get(TITLE.format(song=seeded['id']))

    assert (seeded['id'], free['id']) == (7, 8)
    assert title.status_code == 200 and title.json['title'].strip()
    assert repository.get_stats()['songs_generated'] == 8
    assert len(repository.list_titles()) == 9


def test_generate_from_a_bundle_published_to_s3(tmp_path, aws, make_app, bundle):
    from ml.publish import publish_bundle

    s3 = boto3.client('s3', region_name=REGION)
    s3.create_bucket(Bucket='bakinglyrics-test')
    publish_bundle(bundle, bucket='bakinglyrics-test', prefix='models/lyrics-lstm', client=s3, log=lambda *_: None)

    app = make_app(MODEL_BUCKET='bakinglyrics-test', MODEL_PREFIX='models/lyrics-lstm',
                   MODEL_CACHE_DIR=str(tmp_path / 'cache'))
    seed(app)

    check_song(app.test_client().get(SEED_SONG.format(seed='stayin alive', words=8, artist=1)), 'stayin alive')
    assert (tmp_path / 'cache' / 'test-1' / 'model.onnx').is_file()
