import logging
import traceback

from flask_restplus import Api
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from sqlalchemy.orm.exc import NoResultFound
from config import default

logger = logging.getLogger('baking-api')

api = Api(version='1.0', title='Baking-Lyrics API',
          description='A funny lyrics generator Flask RestPlus powered API')

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)


@api.errorhandler
def default_error_handler():
    message = 'An unhandled exception occurred.'
    logger.exception(message)

    if not default.FLASK_DEBUG:
        return {'message': message}, 500


@api.errorhandler(NoResultFound)
def database_not_found_error_handler():
    logger.warning(traceback.format_exc())
    return {'message': 'A database result was required but none was found.'}, 404
