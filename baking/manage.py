# Generic
import os
import logging
import unittest
import coverage

# Libs
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager

# Own
from baking.main import create_app, db
from baking.main.v1.models import machine_learning as ml


# Test coverage configuration
cov = coverage.Coverage(
    branch=True,
    include='baking/main/*',
    omit=[
        'baking/resources/*.py',
        'baking/static/*.py',
        'baking/migrations/*.py'
    ]
)
cov.start()

logger = logging.getLogger('baking-api')
app = create_app(r'config/development.py')
app.app_context().push()

manager = Manager(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

cov.stop()
cov.save()

cov.html_report()

logger.info('Instantiating  AI models')

model_name_str = app.config['MODEL_NAME_STR']
model_path = app.config['MODELS_PATH']

# Loading Tokenizer
tokenizer_filename = os.path.join(model_path, model_name_str + '.tokenizer.pickle')
embedding_matrix_filename = os.path.join(model_path, model_name_str + '.embmat.npz')
artist_genre_tokenizer_filename = os.path.join(model_path, model_name_str + '.artist_genre_tokenizer.npz')

logger.info('Loading Model Tokenizer...')

tokenizer = ml.Tokenizer(
    model_name=model_name_str,
    artist_genre_tokenizer_path=artist_genre_tokenizer_filename,
    tokenizer_path=tokenizer_filename,
    embedded_matrix_path=embedding_matrix_filename
)
tokenizer.load()

logger.info('Loading Model...')

ml_model = ml.LyricsSkthModel(
    decoder_model_path=os.path.join(model_path, model_name_str + '.model.generator_word.h5'),
    gen_model_context_path=os.path.join(model_path, model_name_str + '.model.generator_context.h5'),
    model_verse_emb_context_path=os.path.join(model_path, model_name_str + '.model.verse_emb_context.h5'),
    model_stv_encoder_path=os.path.join(model_path, model_name_str + '.model.skipthought.h5'),
    tokenizer=tokenizer
)
ml_model.load_model()


@manager.command
def run():

    app.app_context().push()

    # print(app.url_map)

    app.run(host='0.0.0.0',
            port=9090,
            debug=app.config['DEBUG'],
            use_reloader=False)


@manager.command
def test():
    """Runs the unit tests."""
    app.app_context().push()

    tests = unittest.TestLoader().discover('tests', pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if result.wasSuccessful():
        return 0
    return 1


if __name__ == '__main__':
    manager.run()
