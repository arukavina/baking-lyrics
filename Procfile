web: gunicorn baking.manage:app -t 600
release: flask db upgrade
init: python baking/refresh_database.py
