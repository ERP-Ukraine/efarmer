import functools
import traceback

from odoo import api, SUPERUSER_ID
from odoo.modules.registry import Registry
from odoo.http import request, db_list

from .exceptions import BadDatabaseName, InvalidAPIKey, MissedModule, MissedRequiredParameters


def add_env(func):
    """
    Add environment to the request
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        db = kwargs.get('db')
        if not db:
            raise BadDatabaseName()

        if db not in db_list():
            raise BadDatabaseName()

        registry = Registry(db).check_signaling()
        with registry.cursor() as cr:
            # request.env is readonly property, so we have to change "protected" attribute
            request._env = api.Environment(cr, SUPERUSER_ID, {})
            return func(*args, **kwargs)
    return wrapper


def validate(func):
    """
    Does a basic validation of request. Validates:
    - API Keys
    - Database
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Validate database
        db = kwargs.get('db')
        if not db:
            raise BadDatabaseName()

        if db not in db_list():
            raise BadDatabaseName()

        request.session.db = db
        env = request.env(user=SUPERUSER_ID)

        # Validate API Key
        if not hasattr(env['res.config.settings'], 'get_zld_api_key'):
            # Most likely that no module installed
            raise MissedModule()

        key_from_odoo = (env['res.config.settings'].get_zld_api_key() or '').strip()
        key_from_request = (request.httprequest.headers.get('ZLD-API-KEY') or '').strip()

        if not key_from_request or not key_from_odoo:
            raise InvalidAPIKey()

        if key_from_odoo != key_from_request:
            raise InvalidAPIKey()

        return func(*args, **kwargs)
    return wrapper


def required(*arguments):
    """
    Checks required parameters in request data
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Only POST requests are allowed
            data = request.jsonrequest.get('params', {})

            for arg in arguments:
                if arg not in data:
                    raise MissedRequiredParameters(arg)

            return func(*args, **kwargs)
        return wrapper
    return decorator


def catchall(func):
    """
    Catch all exceptions and return them in JSON format.

    This decorator allows to avoid logging exceptions in Odoo logs and provides a way to
    return them in user-friendly format.

    By default, Odoo returns complex error data, including traceback and other information. Also,
    exceptions will be logged in Odoo logs.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return {
                'error': {
                    'code': e.code if hasattr(e, 'code') else -1,
                    'message': str(e),
                    # Add traceback only for development purposes
                    # TODO: Add special setting for this?
                    'traceback': traceback.format_exc(),
                }
            }
    return wrapper
