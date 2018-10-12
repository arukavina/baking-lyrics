# Generic
import logging
import unittest

# Libs
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager

# Own
from baking.main import create_app, db

logger = logging.getLogger('baking-api')
app = create_app(r'config/development.py')
app.app_context().push()

manager = Manager(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)


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
    tests = unittest.TestLoader().discover('tests', pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if result.wasSuccessful():
        return 0
    return 1


if __name__ == '__main__':
    manager.run()
