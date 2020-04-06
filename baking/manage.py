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


logger = logging.getLogger('baking-api')
app = create_app()
app.app_context().push()

manager = Manager(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)


@manager.command
def test():
    """Runs the unit tests without coverage."""
    tests = unittest.TestLoader().discover('tests', pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if result.wasSuccessful():
        return 0
    return 1


@manager.command
def cov():
    """Runs the unit tests with coverage."""
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
    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)
    cov.stop()
    cov.save()

    print('Coverage Summary:')
    cov.report()

    basedir = os.path.abspath(os.path.dirname(__file__))
    covdir = os.path.join(basedir, 'coverage')
    cov.html_report(directory=covdir)

    cov.erase()


@manager.command
def run():

    # print(app.url_map)

    app.run(host='0.0.0.0',
            port=9090,
            debug=app.config['DEBUG'],
            use_reloader=False)


if __name__ == '__main__':
    manager.run()
