# Generic
import logging
import unittest
import coverage

# Libs
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager

# Own
from baking.main import create_app, db


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
