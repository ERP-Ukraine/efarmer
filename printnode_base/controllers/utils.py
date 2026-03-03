# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

import functools
import json

from odoo import api, SUPERUSER_ID
from odoo.modules.registry import Registry
from odoo.http import request
from werkzeug.exceptions import BadRequest


def add_env(func):
    """
    Add environment to the request
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        db = kwargs.get('db')
        if not db:
            raise BadRequest("Database name is required")

        registry = Registry(db).check_signaling()
        with registry.cursor() as cr:
            request.env = api.Environment(cr, SUPERUSER_ID, {})
            return func(*args, **kwargs)
    return wrapper


def extend_request_context(func):
    """
    Update request.env context to ensure correct company selection
    based on incoming controller `context` parameter.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        context = json.loads(kwargs.get('context') or '{}')

        if context:
            request.update_env(
                context=dict(request.env.context, **context)
            )

        kwargs['context'] = context
        return func(*args, **kwargs)

    return wrapper
