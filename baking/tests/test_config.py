# Generic
import os
import unittest
import logging

# Libs
from flask_testing import TestCase

# Own
from baking.manage import app

logger = logging.getLogger('baking-api')


class TestDevelopmentConfig(TestCase):
    def create_app(self):
        app.config.from_object('config.development')
        print('TestDevelopmentConfig')

        return app

    def test_app_is_development(self):
        self.assertFalse(self.app.config['SECRET_KEY'] is 'my_precious')
        self.assertTrue(self.app.config['DEBUG'] is True)
        self.assertFalse(self.app is None)
        self.assertTrue(
            self.app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///' + os.path.join('baking/resources',
                                                                                      'flask_bakinglyrics_main.db')
        )


class TestTestingConfig(TestCase):
    def create_app(self):
        app.config.from_object('config.testing')
        print('TestTestingConfig')

        return app

    def test_app_is_testing(self):
        self.assertFalse(self.app.config['SECRET_KEY'] is 'my_precious')
        self.assertFalse(self.app.config['DEBUG'])
        self.assertTrue(
            self.app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///' + os.path.join('baking/resources',
                                                                                      'flask_bakinglyrics_main.db')
        )


class TestProductionConfig(TestCase):
    def create_app(self):
        app.config.from_object('config.production')
        print('TestProdConfig')

        return app

    def test_app_is_production(self):
        self.assertTrue(self.app.config['DEBUG'] is False)


if __name__ == '__main__':
    unittest.main()
