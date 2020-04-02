from flask_testing import TestCase
from baking.main import create_app, db


class MyTest(TestCase):

    SQLALCHEMY_DATABASE_URI = 'sqlite:////baking/resources/flask_bakinglyrics_main.db'
    TESTING = False

    def create_app(self):

        return create_app(app.config.from_object('config.testing'))

    def setUp(self):

        db.create_all()

    def tearDown(self):

        db.session.remove()
        db.drop_all()
