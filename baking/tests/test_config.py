# Generic
import os
import unittest
import logging

# Libs
from flask_testing import TestCase
from flask_migrate import MigrateCommand
from flask_migrate import Migrate
from flask_script import Manager

# Own
from baking.main import create_app, db

logger = logging.getLogger('baking-api')


class TestDevelopmentConfig(TestCase):
    def create_app(self):
        app = create_app(r'config/development.py')
        print('TestDevelopmentConfig')

        manager = Manager(app)
        Migrate(app, db)
        manager.add_command('db', MigrateCommand)

        return app

    def test_app_is_development(self):
        app = self.create_app()

        self.assertFalse(app.config['SECRET_KEY'] is 'my_precious')
        self.assertTrue(app.config['DEBUG'] is True)
        self.assertFalse(app is None)
        self.assertTrue(
            app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///' + os.path.join('baking/resources',
                                                                                 'flask_bakinglyrics_main.db')
        )


class TestTestingConfig(TestCase):
    def create_app(self):
        app = create_app(r'config/testing.py')
        app.config.from_object('config.testing')
        print('TestTestingConfig')

        return app

    def test_app_is_testing(self):
        app = self.create_app()
        self.assertFalse(app.config['SECRET_KEY'] is 'my_precious')
        self.assertTrue(app.config['DEBUG'])
        self.assertTrue(
            app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///' + os.path.join('baking/resources',
                                                                                 'flask_bakinglyrics_main.db')
        )


class TestProductionConfig(TestCase):
    def create_app(self):
        app = create_app(r'config/development.py')
        app.config.from_object('config.production')
        print('TestProdConfig')

        return app

    def test_app_is_production(self):
        app = self.create_app()
        self.assertTrue(app.config['DEBUG'] is False)


if __name__ == '__main__':
    unittest.main()

