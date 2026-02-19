# See LICENSE file for full copyright and licensing details.

import math
import json
import itertools
from enum import Enum
from typing import Union
from random import randint
from copy import deepcopy

from odoo import _
from odoo.exceptions import UserError
from odoo.addons.integration.tools import flatten_recursive

from ..graphql_templates import GraphQLTemplate
from ..exceptions import ShopifyResourceNotFoundError
from ..connection import GraphQLClient, ExtractNode, _SHOPIFY_BATCH_LIMIT
from ...tools import parse_int, parse_gql_json


class GQLEnum(Enum):

    pass


class GqlDict:

    _body = 'id'
    _gid_name = None
    _api_callable = False
    _tmpl = GraphQLTemplate
    _extract = ExtractNode.extract_raw

    def __init__(self, **kwargs: dict):
        self._ctx = {}
        self._dict = {}
        self._env = None

        self.set(**kwargs)

    def __repr__(self):
        return f'{self._gid_name}({self.id})'

    __str__ = __repr__

    def __getattr__(self, key):
        if key not in self._dict:
            raise AttributeError(f'{self.__class__.__name__} object has no the "{key}" attribute.')
        return self._dict[key]

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super().__setattr__(key, value)
        else:
            self.set(**{key: value})

    def __getitem__(self, key):
        return self._dict.get(key)

    def __setitem__(self, key, value):
        self.set(**{key: value})

    def __bool__(self):
        return bool(self.id)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.gid == other.gid

    def __hash__(self):
        return hash(self.gid)

    @property
    def cls(self):
        return self.__class__

    @property
    def id(self):
        return self.parse_int(self.gid)

    @property
    def id_str(self):
        return str(self.id)

    @property
    def gid(self):
        entity_id = self['id'] or ''

        if not entity_id:
            return entity_id

        return self.create_gid(entity_id)

    @staticmethod
    def parse_int(value, index: int = 0):
        return parse_int(value, index)

    @staticmethod
    def flatten_recursive(data):
        return flatten_recursive(data)

    @staticmethod
    def parse_int_to_str(value, index: int = 0):
        value = parse_int(value, index)
        return str(value) if value else ''

    @property
    def created_at(self):
        return self['createdAt']

    @property
    def updated_at(self):
        return self['updatedAt']

    def ensure_one(self):
        if not self:
            raise ValueError('Expected graphql-orm single object: %s' % self)

    def ensure_new(self):
        if self:
            raise ValueError('Expected graphql-orm non stored object: %s' % self)

    def set(self, **kwargs: dict):
        kwargs_ = parse_gql_json(kwargs)

        entity_id = kwargs_.pop('id', False)

        if entity_id:
            self._set_gid(entity_id)

        self._dict.update(kwargs_)

        return self

    def set_json(self, json_data: str) -> None:
        return self.set(**json.loads(json_data))

    def drop_key(self, *args):
        for key in args:
            self._dict.pop(key, None)

    def key_exist(self, key, not_nullable=False):
        key_exist = key in self._dict

        if key_exist and not_nullable:
            value = self._dict[key]
            if (value is False) or (value is None):
                raise ValueError(f'The "{key}" key found but is nullable ({value}) in {self} object')

        return key_exist

    def raise_if_no_key(self, key, not_nullable=False):
        if not self.key_exist(key, not_nullable=not_nullable):
            raise UserError(f'Key "{key}" not found in {self} object')

    def context(self, key):
        return self._ctx.get(key)

    def add_context(self, **kwargs):
        self._ctx.update(kwargs)

    def reset(self):
        self._dict.clear()
        self.reset_context()

    def reset_context(self):
        self._ctx.clear()

    def default_body(self):
        """Root method for preparing body for query"""
        return self._body

    def to_dict(self):
        return deepcopy(self._dict)

    def create_gid(self, value: Union[str, int]) -> str:
        if isinstance(value, str):
            value = self.parse_int(value)

        if not value or not isinstance(value, int):
            raise ValueError(f'Invalid id value: {value}')

        return f'gid://shopify/{self._gid_name}/{value}'

    def _get_base_schema(self, gid_name: str = None, body: str = None) -> str:
        gid_name_ = gid_name or self._gid_name
        body_ = body or self.default_body()
        return self._tmpl.BASE_SCHEMA % (gid_name_, body_)

    def _new(self, **kwargs: dict):
        instance = self.cls(**kwargs)
        instance._env = self._env

        return instance

    def _read(self) -> None:
        self.ensure_one()

        schema = self._get_base_schema()

        response = self._env.execute(schema, variables={'id': self.gid})
        data = self._extract(response, 'data.node', dict)

        self.set(**data)

    def _set_gid(self, value: Union[str, int]) -> str:
        self._dict['id'] = self.create_gid(value)
        return self['id']

    def _set_pseudo_id(self):
        self.set(id=f'100500{randint(10000, 99999)}')  # ADD pseudo ID to avoid errorsraise_if_no_key


class ShopifyResourceBase:

    def __init__(self, url: str, token: str, version: str, debug: bool):
        self._client = GraphQLClient(url, token, version, debug)
        self._env = None

    def new(self, **kwargs: dict):
        instance = self.__class__(self._client.url, self._client.token, self._client.version, self._client._debug)
        instance._env = self._env

        if kwargs:
            instance.set(**kwargs)

        return instance

    def execute(self, query: str, variables: dict = None, user_errors_path: str = ''):
        return self._client.execute(query, variables=variables, user_errors_path=user_errors_path)


class CreateMixin:

    MUTATION_CREATE = None

    def create(self, *args, **kwargs):
        raise NotImplementedError('Create method is not implemented for this resource')


class ReadMixin:

    _body = ''
    _request_name = None
    _infinity = math.inf
    _request_limit = _SHOPIFY_BATCH_LIMIT

    @property
    def _request_name_plural(self):  # TODO: think about..
        return f'{self._request_name}s'

    @property
    def cursor(self):
        return self.context('hasNextPage') and self.context('endCursor') or ''

    def read(self, body: str = '', add_fields: str = '', return_raw: bool = False) -> dict:
        self.ensure_one()

        # 1. Prepare body query
        body_ = body or self.default_body()

        if add_fields:
            body_ += f'\n {add_fields}'

        # 2. Build query
        query = self._use_pk_template(self.gid, body_)

        # 3. Execute query
        response = self.execute(query)

        # 4. Extract response
        result = self._extract_response(response) or {}

        # 5. Return raw result if requested
        if return_raw:
            return result

        # 6. If no result, return new instance
        if not result:
            self.reset()
        else:
            # 7. Set result to instance
            if 'id' not in result:
                result['id'] = self.gid

            self.set(**result)

        return self.to_dict()

    def get_schema(self):
        data = self.execute(self._tmpl.MODEL_SCHEMA % self._gid_name)
        return self._extract(data, 'data.__type', dict)

    def get_by_pk(self, pk: int, body: str = '', add_fields: str = '', raise_if_not_found: bool = True):
        self.set(id=pk)
        gid = self.gid

        self.read(body=body, add_fields=add_fields)

        if not self and raise_if_not_found:
            raise ShopifyResourceNotFoundError(
                _('The "%s" resource was not found in the external system!') % gid
            )

        return self

    def get_batch(
        self,
        body: str = None,
        arguments: str = None,
        filter_params: Union[dict, str] = None,
        limit: int = _request_limit,
    ):
        # 1. Prepare request limit
        if limit == self._infinity:
            request_limit = self._request_limit
            iterations = itertools.count()
        elif limit <= self._request_limit:
            request_limit = limit
            iterations = range(1)
        else:
            request_limit = self._request_limit
            iterations = range((limit // self._request_limit) + 1)

        # 1.1. Prepare query arguments
        _values = f'first: {request_limit}'

        if arguments:
            _values += f', {arguments}'

        # 1.2. Prepare filter parameters
        if filter_params:
            if isinstance(filter_params, str):
                _values += f', query: "{filter_params}"'
            elif isinstance(filter_params, dict):
                _values += ', query: "%s"' % ' '.join([f'{k}:{v}' for k, v in filter_params.items()])

        # 2. Execute query
        result = []
        for __ in iterations:
            # 2.1. Prepare query values
            if self.cursor:
                values = f'{_values}, after: "{self.cursor}"'
            else:
                values = _values

            query = self._use_batch_template(values, (body or self.default_body()))

            response = self.execute(query)
            response_list = self._extract_response(response, key=self._request_name_plural)

            result.extend(response_list)

            if not self.cursor or len(result) >= limit:
                break

        # 3. Limit result if requested
        if limit != self._infinity:
            result = result[:limit]

        # 4. Return new records from response
        return [self.new(**vals) for vals in result]

    def get_by_ids(self, ids: list, body: str = None) -> list:
        result = []
        limit = self._request_limit

        # 1. Prepare ids as GIDs
        ids_ = [self.create_gid(x) for x in ids]

        # 2. Build query
        query = self._tmpl.QUERY_BATCH_BY_IDS % (self._gid_name, body or self.default_body() or 'id')

        # 3. Execute query
        for chunk in (ids_[i:i + limit] for i in range(0, len(ids_), limit)):
            response = self.execute(query, variables={'ids': chunk})
            response_chunk = self._extract_response(response, key='nodes')

            result.extend([self.new(**vals) for vals in response_chunk if vals])

        return result

    def _use_pk_template(self, gid: str, body: str) -> str:
        return '{ %s(id: "%s") { %s } }' % (self._request_name, gid, body)

    def _use_batch_template(self, values: str, body: str) -> str:
        query_ = '{ %s(%s) { pageInfo { endCursor hasNextPage } edges { node { %s } } } }'
        return query_ % (self._request_name_plural, values, body)

    def _extract_response(self, data: dict, key: str = None, cursor_key: str = 'pageInfo') -> Union[dict, list]:
        data_ = self._base_extract(data, key=key, cursor_key=cursor_key)
        return parse_gql_json(data_)

    def _base_extract(self, data: dict, key: str = None, cursor_key: str = 'pageInfo') -> Union[dict, list]:
        key_ = key or self._request_name
        data_ = self._extract(data, f'data.{key_}', dict)  # TODO: dict or list?

        self._save_cursor(data_, cursor_key=cursor_key)

        return data_

    def _save_cursor(self, data: dict, cursor_key: str = 'pageInfo') -> None:
        if isinstance(data, dict):
            if cursor_key == 'pageInfo':
                value = data.pop(cursor_key, False) or {}
            else:
                value = self._extract(data, cursor_key, dict)
        else:
            value = {}

        if value:
            self.add_context(**value)
        else:
            self.reset_context()


class UpdateMixin:

    MUTATION_UPDATE = None

    def update(self, *args, **kwargs):
        raise NotImplementedError('Update method is not implemented for this resource')


class DeleteMixin:

    MUTATION_DELETE = None

    def delete(self):
        self.ensure_one()
        return self.execute(self.MUTATION_DELETE, variables={'id': self.gid})

    def delete_by_pk(self, pk: int):
        self.set(id=pk)
        return self.delete()


class ShopifyResourceRead(GqlDict, ShopifyResourceBase, ReadMixin):

    _api_callable = True

    def __init__(self, url: str, token: str, version: str, debug: bool):
        GqlDict.__init__(self)
        ShopifyResourceBase.__init__(self, url, token, version, debug)


class ShopifyResourceUpdate(ShopifyResourceRead, UpdateMixin):

    def update(self, *args, **kwargs):
        raise NotImplementedError('Update method is not implemented for this resource')
