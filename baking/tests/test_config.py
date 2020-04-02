# Generic
import os
import unittest
import logging

# Libs
from flask import current_app as app
from flask_testing import TestCase

logger = logging.getLogger('baking-api')


class TestDevelopmentConfig(TestCase):
    def create_app(self):
        app.config.from_object('config.development')
        return app

    def test_app_is_development(self):
        self.assertFalse(app.config['SECRET_KEY'] is 'my_precious')
        self.assertTrue(app.config['DEBUG'] is True)
        self.assertFalse(app is None)
        self.assertTrue(
            app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///' + os.path.join('baking/resources',
                                                                                 'flask_bakinglyrics_main.db')
        )


class TestTestingConfig(TestCase):
    def create_app(self):
        app.config.from_object('config.testing')
        return app

    def test_app_is_testing(self):
        self.assertFalse(app.config['SECRET_KEY'] is 'my_precious')
        self.assertTrue(app.config['DEBUG'])
        self.assertFalse(
            app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///' + os.path.join('baking/resources',
                                                                                 'flask_bakinglyrics_main.db')
        )


class TestProductionConfig(TestCase):
    def create_app(self):
        app.config.from_object('config.production')
        return app

    def test_app_is_production(self):
        self.assertTrue(app.config['DEBUG'] is False)


if __name__ == '__main__':
    unittest.main()
