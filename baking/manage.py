"""
WSGI entry point and Flask CLI target.

The app is built from the config file named by the APP_CONFIG_FILE environment variable
(or a `.env` file at the repository root), e.g. APP_CONFIG_FILE=config/development.py.

Usage:
    gunicorn baking.manage:app
    flask --app baking.manage run --port 9090      # development server (the historical port is 9090)
    flask --app baking.manage db upgrade           # Flask-Migrate commands (db init/migrate/upgrade/...)
    python -m baking.manage                        # same as `flask run` on 0.0.0.0:9090

Tests are run with pytest (`uv run pytest`).
"""

# Own
from baking.main import create_app

app = create_app()


def run(host='0.0.0.0', port=9090):
    """Runs the development server (replacement for the old Flask-Script `run` command)."""
    app.run(host=host,
            port=port,
            debug=app.config['DEBUG'],
            use_reloader=False)


if __name__ == '__main__':
    run()
