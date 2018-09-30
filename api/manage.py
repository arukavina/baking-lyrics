# Generic
import unittest
import logging
import coverage

# Libs
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from flask_login import login_user, logout_user, current_user
from flask_login import LoginManager

# Own
from api.database.models import User
from api.v1.models.oauth import OAuthSignIn
from api.v1 import create_app, db, api, limiter
from api.v1.endpoints.artists import ns as bands_namespace
from api.v1.endpoints.genres import ns as genres_namespace
from api.v1.endpoints.songs import ns as lyrics_namespace
from api.v1.endpoints.artificial_titles import ns as artificial_titles_namespace
from api.v1.endpoints.artificial_songs import ns as artificial_songs_namespace
from api.v1.endpoints.general import ns as general_namespace

logger = logging.getLogger('baking-api')

app = create_app(None)

app.app_context().push()

manager = Manager(app)

migrate = Migrate(app, db)

manager.add_command('db', MigrateCommand)

limiter.init_app(app)

# Test coverage configuration
COV = coverage.coverage(
    branch=True,
    include='api/*',
    omit=[
        'api/resources/*.py',
        'api/static/*.py',
        'api/migrations/*.py'
    ]
)
COV.start()

# Login Manager
lm = LoginManager(app)
lm.login_view = 'login'


@app.route("/")
@limiter.exempt
def index():
    return render_template("index.html")


@app.route("/login")
@limiter.exempt
def login():
    return render_template("login.html")


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    if not current_user.is_anonymous:
        return redirect(url_for('login'))
    oauth = OAuthSignIn.get_provider(provider)
    return oauth.authorize()


@app.route('/callback/<provider>')
def oauth_callback(provider):
    if not current_user.is_anonymous:
        return redirect(url_for('login'))
    oauth = OAuthSignIn.get_provider(provider)
    social_id, username, email = oauth.callback()
    if social_id is None:
        flash('Authentication failed.')
        return redirect(url_for('login'))
    user = User.query.filter_by(social_id=social_id).first()
    if not user:
        user = User(social_id=social_id, nickname=username, email=email)
        db.session.add(user)
        db.session.commit()
    login_user(user, True)
    return redirect(url_for('index'))


@manager.command
def run():

    blueprint = Blueprint('api', __name__, url_prefix='/api/v1')
    api.init_app(blueprint)

    api.add_namespace(bands_namespace)
    api.add_namespace(genres_namespace)
    api.add_namespace(lyrics_namespace)
    api.add_namespace(artificial_titles_namespace)
    api.add_namespace(artificial_songs_namespace)
    api.add_namespace(general_namespace)

    app.register_blueprint(blueprint)

    app.app_context().push()

    # print(app.url_map)

    app.run(debug=app.config['DEBUG'], use_reloader=False)


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
