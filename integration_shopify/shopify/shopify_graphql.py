# See LICENSE file for full copyright and licensing details.

import logging
import weakref

from . import resources

from .connection import GraphQLClient
from .resources.base import GQLEnum


_logger = logging.getLogger(__name__)


class GQLModel:
    """GQL Model: just a descriptor wrapper for the ShopifyResourceRead"""

    def __init__(self, cls):
        self._cls = cls

    def __get__(self, instance: 'ShopifyGraphQL', owner):
        # Instantiate the ShopifyResourceRead inherited class
        if getattr(self._cls, '_api_callable', False):
            record = self._cls(instance.url, instance.token, instance.version, instance._debug)
        elif issubclass(self._cls, GQLEnum):
            record = self._cls
        else:
            record = self._cls()

        record._env = weakref.proxy(instance)

        return record


class ShopifyGraphQL(GraphQLClient):

    @classmethod
    def update_class(cls, **kwargs):
        """Patch method for extensions"""
        for key, value in kwargs.items():
            setattr(cls, key, GQLModel(value))


def update_shopify_graphql_class():
    """Update the ShopifyGraphQL class with the GQLModel descriptors"""
    for name in dir(resources):
        # Only consider attributes that start with an alphabetic character
        if not name or not (name[0].isalpha() and name[0].isupper()):
            continue

        cls = getattr(resources, name)

        try:
            if hasattr(cls, '_gid_name') or issubclass(cls, GQLEnum):
                ShopifyGraphQL.update_class(**{name: cls})
        except Exception as e:
            _logger.error('Error updating %s: %s', name, e)


update_shopify_graphql_class()
