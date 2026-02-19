# See LICENSE file for full copyright and licensing details.

import base64
import logging
import hashlib
import json
import io
import inspect
import mimetypes
import os
import re
import time

from collections import defaultdict, namedtuple
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, date, time as dt_time
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from functools import wraps, partial
from itertools import groupby
from operator import attrgetter
from pprint import pprint
from time import sleep
from typing import Any, Callable, List, Union, Dict, Type
from markupsafe import Markup

from psycopg2 import OperationalError
from PIL import Image, UnidentifiedImageError

from odoo import models, _
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY
from odoo.tools.image import IMAGE_MAX_RESOLUTION
from odoo.tools.safe_eval import safe_eval
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.misc import groupby as odoo_groupby


try:
    # Prefer import from integration_queue_job if available
    from odoo.addons.integration_queue_job.exception import RetryableJobError
except ImportError:
    # Fallback if queue_job is not installed
    from odoo.addons.queue_job.exception import RetryableJobError

from .exceptions import ErrorStore


_logger = logging.getLogger(__name__)

IS_TRUE = '1'
IS_FALSE = '0'

CLIENT_LIMIT = 8
SERVER_LIMIT = 5

CLIENT_TIMEOUT = 4
SERVER_TIMEOUT = 2

# PIL: add possibility to load all available file format drivers
Image._initialized = 1
Image.preinit()


class DateTimeJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles datetime objects, dates, and other non-serializable types.

    This class extends the standard JSON encoder to handle:
    - datetime objects (converted to ISO format strings)
    - date objects (converted to ISO format strings)
    - time objects (converted to ISO format strings)
    - Decimal objects (converted to float)
    - Enum objects (converted to their values)
    - Markup objects (converted to strings)

    Usage:
        encoder = DateTimeJSONEncoder()
        json_string = encoder.encode(data_with_datetime)

        # Or use directly with json.dumps
        json_string = json.dumps(data_with_datetime, cls=DateTimeJSONEncoder)
    """

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, dt_time):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, Markup):
            return str(obj)
        elif hasattr(obj, '__dict__'):
            # Handle objects with __dict__ attribute
            return obj.__dict__
        elif hasattr(obj, '__slots__'):
            # Handle objects with __slots__
            return {slot: getattr(obj, slot, None) for slot in obj.__slots__}

        return super().default(obj)


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    Safely serialize Python objects to JSON string, handling datetime objects.

    Args:
        obj: The object to serialize
        **kwargs: Additional arguments to pass to json.dumps

    Returns:
        JSON string representation of the object

    Example:
        data = {'timestamp': datetime.now(), 'name': 'test'}
        json_str = safe_json_dumps(data)
    """
    return json.dumps(obj, cls=DateTimeJSONEncoder, **kwargs)


def _compute_checksum(b64_bytes):  # Like ir.attachment._compute_checksum()
    if not b64_bytes:
        return None
    return hashlib.sha1(base64.b64decode(b64_bytes)).hexdigest()


def _guess_mimetype(data):
    if not data:
        return None

    raw_bytes = base64.b64decode(data)
    mimetype = guess_mimetype(raw_bytes)

    # If we got the default value (application/octet-stream), let's try the Pillow library
    if mimetype != 'application/octet-stream':
        return mimetype

    try:
        with io.BytesIO(raw_bytes) as f, Image.open(f) as img:
            extension = img.format
    except UnidentifiedImageError:
        return mimetype

    return Image.MIME[extension]


def _verify_image_data(data: bytes, logger_name: str):
    try:
        img = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as e:
        _logger.error(f'{logger_name} image error: ' + str(e))
        return False

    w, h = img.size
    resolution_ok = w * h <= IMAGE_MAX_RESOLUTION

    if not resolution_ok:
        _logger.error(f'{logger_name} image error: Image resolution is higher than Odoo allows')
        return False

    return resolution_ok


def make_list_if_not(value):
    if not isinstance(value, list):
        value = [value]

    return value


def is_translated_value(value) -> bool:
    return isinstance(value, dict) and ('language' in value) and value['language']


def parse_translated_value(value: dict, lang: str):
    if not is_translated_value(value):
        return value

    return value['language'].get(lang)


def not_implemented(method):
    def wrapper(self, *args, **kw):
        raise NotImplementedError(_(
            'This functionality is not yet implemented. Please contact our support team (%(support_url)s) or '
            'your Odoo partner for further details.'
        ) % 'https://support.ventor.tech/')
    return wrapper


def raise_requeue_job_on_concurrent_update(method):
    @wraps(method)
    def wrapper(self, *args, **kw):
        try:
            result = method(self, *args, **kw)
            # flush_all() is needed to push all the pending updates to the database
            self.env.flush_all()
            return result
        except OperationalError as e:
            if e.pgcode in PG_CONCURRENCY_ERRORS_TO_RETRY:
                raise RetryableJobError(str(e))
            else:
                raise

    return wrapper


def add_dynamic_kwargs(method):
    def __add_dynamic_kwargs(*ar, **dynamic_kwargs):
        def _add_dynamic_kwargs(*args, **kwargs):
            return method(*ar, *args, **kwargs, **dynamic_kwargs)
        return _add_dynamic_kwargs
    return __add_dynamic_kwargs


def normalize_uom_name(uom_name):
    uom_name = uom_name.lower()

    # lbs, kgs - is incorrect name
    if uom_name in ['lbs', 'kgs']:
        uom_name = uom_name[:-1]

    return uom_name


def xml_to_dict_recursive(root):
    """
    :params:
        from xml.etree import ElementTree
        root = ElementTree.XML(xml_to_convert)
    """
    if not len(list(root)):
        return {root.tag: root.text}
    return {root.tag: list(map(xml_to_dict_recursive, list(root)))}


def escape_trash(value, allowed_chars=None, max_length=None, lowercase=False):
    """
    Escape special characters in a string.

    :param value: The input string.
    :param allowed_chars: A string containing characters that should be preserved.
                          All other characters will be replaced.
    :param max_length: The maximum length of the resulting string.
    :return: The escaped string.
    """
    if allowed_chars:
        # Use a regular expression to match characters not in allowed_chars
        pattern = r'[^{re.escape(allowed_chars)}]+'
    else:
        # If allowed_chars is not provided, replace all non-alphanumeric characters
        pattern = r'[^0-9a-zA-Z]+'

    # Apply the substitution
    value = re.sub(pattern, '-', value, flags=re.IGNORECASE)

    # Limit the length of the result
    if max_length:
        value = value[:max_length]

    if lowercase:
        value = value.lower()

    return value.strip('-')


def round_float(value, decimal_precision):
    value = Decimal(str(value))

    # Convert the precision into a quantize string format like '.00'
    quantize_str = '.' + '0' * decimal_precision

    # Round the value using the quantize string
    rounded_value = value.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
    return float(rounded_value)


def flatten_recursive(lst):
    """
    Unwrap the nested list of nested lists.

    :lst: [1, [2, [3, 4], [5], [6, [7, 8]]], [9], 10]
    :output: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    """
    def _flatten_recursive(lst):
        for item in lst:
            if isinstance(item, list):
                yield from _flatten_recursive(item)
            else:  # Don't touch this `else`
                yield item

    return list(_flatten_recursive(lst))


def _is_valid_email(email):
    """
    Validate the given email address.
    """
    email_regex = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    return bool(re.match(email_regex, email))


def freeze_arguments(*args_to_copy: str) -> Callable:
    """
    Decorator to protect specified arguments passed to a method from being modified.
    Args:
        *args_to_copy: The names of the arguments to copy.
    Returns:
        A decorator function.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Deepcopy specified arguments
            for arg_name in args_to_copy:
                if arg_name in bound_args.arguments:
                    try:
                        bound_args.arguments[arg_name] = deepcopy(bound_args.arguments[arg_name])
                    except Exception as e:
                        raise TypeError(f'Failed to deepcopy argument "{arg_name}": str({e})')

            return func(*bound_args.args, **bound_args.kwargs)

        return wrapper

    return decorator


def track_changes(include_related_fields=None, sensitive_fields=None, exclude_fields=None):
    """
    Decorator to log field changes in chatter.

    - Logs field changes before and after `write()`.
    - Supports One2many fields (logs related record changes).
    - Masks sensitive fields (e.g., passwords, API keys) dynamically.

    :param include_related_fields: list of One2many fields to track (e.g., ['field_ids']).
    :param sensitive_fields: list of fields to mask (e.g., ['password', 'api_key']).
    :param exclude_fields: list of fields to exclude from tracking (e.g., ['name']).

    Usage:
        @track_changes(
            include_related_fields=['field_ids'], sensitive_fields=['password', 'api_key'], exclude_fields=['name'],
        )

    Requires:
        - Model must inherit from 'mail.thread'.
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, vals, *args, **kwargs):
            changes = defaultdict(dict)
            related_changes = defaultdict(dict)

            exclude_fields_set = set(exclude_fields or [])

            def mask_sensitive_data(value):
                """Mask sensitive values (e.g., API keys, passwords)."""
                if not isinstance(value, str):
                    return value

                length = len(value)
                if length == 1:
                    return 'X'

                return value[:1] + 'X' * (length - 1) if length <= 5 else value[:-5] + 'X' * 5

            def collect_values(record, state):
                """
                Collect changes in fields.
                """
                for field in vals:
                    if field not in record._fields or field in include_related_fields:
                        continue
                    if field in exclude_fields_set:
                        continue

                    if isinstance(record[field], models.Model):
                        value = record[field].mapped('display_name') or []
                    else:
                        value = record[field]

                    value = f'{value} (ID: {record.id})'

                    if value and sensitive_fields and field in sensitive_fields:
                        value = mask_sensitive_data(value)

                    if field not in changes[record.id]:
                        changes[record.id][field] = {}
                    changes[record.id][field][state] = value

            def collect_updated_related_changes(record, state):
                """
                Collect changes in related fields.
                """
                for field in include_related_fields:
                    if field not in vals or field not in record._fields:
                        continue

                    related_model = self.env[record._fields[field].comodel_name]

                    for value in vals[field]:
                        if not isinstance(value, list) or len(value) < 3:
                            continue

                        operation_type, related_id, change_data = value
                        if operation_type != 1:  # 1 - update
                            continue

                        related_record = related_model.browse(related_id)
                        related_record_name = related_record.display_name

                        if field == 'field_ids':
                            value = getattr(related_record, 'value', related_record_name)
                        else:
                            value = related_record_name

                        value = f'{value} (ID: {related_record.id})'

                        if value and related_record_name in sensitive_fields:
                            value = mask_sensitive_data(value)

                        field_key = f'{related_record._description} ({related_record_name})'

                        if field_key not in related_changes[record.id]:
                            related_changes[record.id][field_key] = {}
                        related_changes[record.id][field_key][state] = value

            def collect_added_removed_related_changes(record):
                """
                Collect added/removed related records.
                """
                for field in include_related_fields:
                    if field not in vals or field not in record._fields:
                        continue

                    related_model = self.env[record._fields[field].comodel_name]

                    for val in vals[field]:
                        if not isinstance(val, list):
                            continue

                        operation_type, related_id, *change_data = val
                        change_data = change_data[0] if change_data else {}

                        if operation_type == 0:  # 0 - create
                            new_values = [
                                f'{k}: {mask_sensitive_data(v) if k in sensitive_fields else v}'
                                for k, v in change_data.items()
                                if v
                            ]

                            field_key = f'{related_model._description} ({related_id})'

                            if field_key not in related_changes[record.id]:
                                related_changes[record.id][field_key] = {}
                            related_changes[record.id][field_key]['new'] = ', '.join(new_values)

                        elif operation_type == 2:  # 2 - delete
                            related_record = related_model.browse(related_id)
                            related_record_name = related_record.display_name

                            if field == 'field_ids':
                                value = getattr(related_record, 'value', related_record_name)
                            else:
                                value = related_record_name

                            value = f'{value} (ID: {related_record.id})'

                            if value and related_record_name in sensitive_fields:
                                value = mask_sensitive_data(value)

                            field_key = f'{related_record._description} ({related_record_name})'

                            if field_key not in related_changes[record.id]:
                                related_changes[record.id][field_key] = {}
                            related_changes[record.id][field_key]['old'] = value or related_record_name

            # 1. Collect old values before changes
            for record in self:
                collect_values(record, 'old')

            # 2. Collect old values of related records
            if include_related_fields:
                for record in self:
                    collect_updated_related_changes(record, 'old')

            # 3. Collect added/removed related records
            if include_related_fields:
                for record in self:
                    collect_added_removed_related_changes(record)

            # 4. Execute original method (write)
            res = method(self, vals, *args, **kwargs)

            # 5. Collect new values after changes
            for record in self:
                collect_values(record, 'new')

            # 6. Collect new values of related records
            if include_related_fields:
                for record in self:
                    collect_updated_related_changes(record, 'new')

            # 7. Log changes in chatter
            for record_id, fields_data in changes.items():
                record = self.browse(record_id)

                for field, values in fields_data.items():
                    if values.get('old') != values['new']:
                        msg = Markup(_('<b>{}</b> parameter changed:<i> "{}" → "{}"</i>').format(
                            record._fields[field].string, values.get('old'), values['new']
                        ))
                        record._message_log(body=msg, message_type='comment', author_id=self.env.user.partner_id.id)

            # 8. Log related records changes in chatter
            for record_id, fields_data in related_changes.items():
                record = self.browse(record_id)

                for field_name, values in fields_data.items():
                    old_value = values.get('old', '')
                    new_value = values.get('new', '')

                    if all([old_value, new_value]):
                        if old_value != new_value:
                            msg = Markup(_(
                                '🔄 <b>{}</b> field changed:<i> "{}" → "{}"</i>').format(
                                    field_name, old_value, new_value)
                            )
                        else:
                            msg = Markup(_(
                                '🔄 <b>{}</b> field changed:<i> Record updated: "{}"</i>').format(
                                    field_name, new_value)
                            )

                        record._message_log(body=msg, message_type='comment', author_id=self.env.user.partner_id.id)

                    elif new_value and not old_value:
                        msg = Markup(_(
                            '➕ <b>{}</b> field added:<i> "{}"</i>').format(
                                field_name, new_value,
                            )
                        )
                        record._message_log(body=msg, message_type='comment', author_id=self.env.user.partner_id.id)

                    elif old_value and not new_value:
                        msg = Markup(_(
                            '➖ <b>{}</b> field removed:<i> "{}"</i>').format(
                                field_name, old_value,
                            )
                        )
                        record._message_log(body=msg, message_type='comment', author_id=self.env.user.partner_id.id)

            return res

        return wrapper

    return decorator


class ProductType(Enum):
    PRODUCT_TEMPLATE = 'product.template'
    PRODUCT_PRODUCT = 'product.product'

    @property
    def is_template(self):
        return self == ProductType.PRODUCT_TEMPLATE

    @property
    def is_variant(self):
        return self == ProductType.PRODUCT_PRODUCT


class ActionType(Enum):
    """
        "none" - mapping is actual, no needs to do smth.
        "pending" - initial state, need to check and decide what to do. If value didn't change - drop this mapping.
        "assign" - mapping is actual, but need to be reassigned to the other product.
        "create" - mapping is assigned to product with id=False and but need to be created in the external system.
    """

    NONE = 'none'
    PENDING = 'pending'
    ASSIGN = 'assign'
    CREATE = 'create'

    @property
    def to_create(self):
        return self == ActionType.CREATE

    @property
    def to_none(self):
        return self == ActionType.NONE

    @property
    def to_assign(self):
        return self == ActionType.ASSIGN


@dataclass
class ExternalImage:

    integration_id: int
    code: str
    name: str
    src: str
    is_cover: bool
    template_code: str
    ttype: ProductType

    sku: str = None
    b64_bytes: bytes = None
    variant_code: str = None
    verbose_name: str = None
    product_image_mapping_id: int = None
    action_type: ActionType = ActionType.NONE

    def __repr__(self):
        name = f'action_type={self.action_type.value}, code={self.code}, '
        name += f'template_code={self.template_code}, variant_code={self.variant_code}, is_cover={self.is_cover}'
        return f'<{self.__class__.__name__}: {name}>'

    __str__ = __repr__

    @property
    def code_int(self):
        if not self.code:
            return 0
        return int(self.code.rsplit('/', 1)[-1])

    @property
    def to_create(self):
        return self.action_type.to_create

    @property
    def to_none(self):
        return self.action_type.to_none

    @property
    def to_assign(self):
        return self.action_type.to_assign

    @property
    def is_template(self):
        return self.ttype.is_template

    @property
    def is_variant(self):
        return self.ttype.is_variant

    @property
    def is_template_cover(self):
        return bool(self.is_template and self.is_cover)

    @property
    def is_variant_cover(self):
        return bool(self.is_variant and self.is_cover)

    @property
    def mimetype(self):
        return _guess_mimetype(self.b64_bytes)

    @property
    def extension(self):
        return mimetypes.guess_extension(self.mimetype)

    @property
    def checksum(self):
        return _compute_checksum(self.b64_bytes)

    @property
    def b64_ascii(self):
        return base64.b64decode(self.b64_bytes)

    def update(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)

    @classmethod
    def from_mapping(cls, mapping):
        """
        mapping: models.Model.integration.product.image.mapping
        """
        return cls(
            code=mapping.code,
            name=mapping.name,
            src=mapping.src,
            ttype=ProductType(mapping.ttype),
            template_code=mapping.template_code,
            variant_code=mapping.variant_code,
            is_cover=mapping.is_cover,
            b64_bytes=mapping.get_b64_data(),
            sku=mapping.get_external_sku(),
            verbose_name=escape_trash(mapping.res_name, max_length=100),
            action_type=ActionType(mapping.action_type),
            product_image_mapping_id=mapping.id,
            integration_id=mapping.integration_id.id,
        )

    def to_dict(self):  # It needs for the `integration.import.product.wizard`
        return {
            'code': self.code,
            'template_code': self.template_code,
            'variant_code': self.variant_code,
            'is_cover': self.is_cover,
            'src': self.src,
        }

    def _to_external_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'src': self.src,
            'template_code': self.template_code,
            'integration_id': self.integration_id,
        }

    def _to_mapping_dict(self):
        return {
            **self._to_external_dict(),
            'ttype': self.ttype.value,
            'is_cover': self.is_cover,
            'checksum': self.checksum,
            'variant_code': self.variant_code,
            'action_type': self.action_type.value,
        }

    def _get_filename(self):
        return f'{self.verbose_name}{self.extension}'

    def _get_unique_filename(self):
        return f'{self.template_code}-{self.checksum}{self.extension}'


class Adapter:
    """Class wrapper for Integration API-Client."""

    def __init__(self, adapter_core, env):
        self.__cache_core = adapter_core
        self._env = env

    def __repr__(self):
        return f'<{self.__class__.__name__} at {hex(id(self))}: [{self.__cache_core}]>'

    def __getattr__(self, name):
        attr = getattr(self.__cache_core, name)
        if hasattr(attr, '__name__') and attr.__name__ == '__add_dynamic_kwargs':
            dynamic_kwargs = self.__get_dynamic_kwargs()
            return attr(**dynamic_kwargs)
        return attr

    def __get_dynamic_kwargs(self):
        return {
            '_env': self._env,
        }

    @property
    def cls(self):
        return self.__cache_core.__class__


class AdapterHub:

    _adapter_hub = dict()

    @staticmethod
    def get_key(integration):
        return f'{integration.id}-{os.getpid()}'

    @classmethod
    def set_core_cls(cls, integration, key):
        core = integration._build_adapter_core()
        cls._adapter_hub[key] = core
        _logger.info('Set integration api-client core: %s, %s', key, core)
        return core

    @classmethod
    def erase_core_cls(cls, key):
        core = cls._adapter_hub.pop(key, False)
        _logger.info('Erase integration api-client core: %s, %s', key, core)

    def get_core(self, integration):
        key = self.get_key(integration)

        if not self._adapter_hub.get(key):
            core = AdapterHub.set_core_cls(integration, key)
        else:
            core = self._adapter_hub[key]
            if core._adapter_hash != integration.get_hash():
                AdapterHub.erase_core_cls(key)
                core = AdapterHub.set_core_cls(integration, key)

        core.activate_adapter()
        _logger.info('Get integration api-client core: %s, %s', key, core)
        return core


class PriceList:
    """
        Data-class for convenient handling price list items during export
        and analysing saved result.
    """

    _proxy_cls = 'integration.product.pricelist.item.external'

    def __init__(self, integration, res_id, res_model, ext_id, prices, force):
        self.int_id = integration.id
        self._env = integration.env

        self._res_id = res_id
        self._res_model = res_model
        self.ext_id = ext_id
        self.prices = prices
        self.force_sync_pricelist = force

        self._result = list()
        self._unlink_list = list()

    def __repr__(self):
        name = f'{self.int_id}: {self._res_model}({self._res_id},)'
        return f'<{self.__class__.__name__}: [{name}]>'

    @classmethod
    def from_tuple(cls, tpl, integration):
        return cls(integration, *tpl)

    @property
    def env(self):
        return self._env

    @property
    def proxy_cls(self):
        return self.env[self._proxy_cls]

    @property
    def result(self):
        return self._result

    @property
    def unlinked(self):
        return self._unlink_list

    @property
    def tmpl_id(self):
        if self._res_model == 'product.template':
            return self._res_id
        return False

    @property
    def var_id(self):
        if self._res_model == 'product.product':
            return self._res_id
        return False

    def join_external_groups(self):
        return '|'.join(x['external_group_id'] for x in self.prices)

    def parsed_items(self):
        return [x['_item_id'] for x in self.prices]

    def parsed_external_items(self):
        res = sum([x['_external_item_ids'] for x in self.prices], [])
        return list(set(res))

    def update_result(self, res):
        self._result.append(res)

    def update_unlinked(self, ids):
        self._unlink_list = ids

    def dump(self):
        self._save_result_db()
        return f'{self._res_model}({self._res_id},) / {self.ext_id}: {self.result}'

    def _parse_template_and_combination(self):
        if self._res_model == 'product.template':
            return self.ext_id, IS_FALSE
        return self.ext_id.split('-', 1)

    def _save_result_db(self):
        self._drop_unlinked()

        vals_list = list()
        default_vals = self._default_vals()

        for item_id, ext_item_id in self.result:
            if not ext_item_id:
                continue
            self._drop_legasy(item_id)
            vals = {
                'item_id': item_id,
                'external_item_id': ext_item_id,
                **default_vals,
            }
            vals_list.append(vals)

        return self.proxy_cls.create(vals_list)

    def _drop_unlinked(self):
        # Drop records which were dropped during export
        # Maybe it's not essential because of the first step already did it
        domain = [
            ('integration_id', '=', self.int_id),
            ('external_item_id', 'in', self.unlinked),
        ]
        records = self.proxy_cls.search(domain)
        return records.unlink()

    def _drop_legasy(self, item_id):
        # Drop records relates to certain `item_id`
        domain = self._default_domain()
        domain.append(('item_id', '=', item_id))
        records = self.proxy_cls.search(domain)
        return records.unlink()

    def _default_domain(self):
        vals = self._default_vals()
        return [(k, '=', v) for k, v in vals.items()]

    def _default_vals(self):
        return {
            'variant_id': self.var_id,
            'template_id': self.tmpl_id,
            'integration_id': self.int_id,
        }


PTuple = namedtuple('Product', 'id name barcode ref parent_id skip_ref joint_namespace')


class ProductTuple(PTuple):
    """Convenient handling separate TemplateHub list record"""

    @property
    def format_id(self):
        return f'{self.parent_id}-{self.id}' if self.parent_id else self.id

    @property
    def format_name(self):
        name = self.name or False

        if isinstance(self.name, dict) and 'language' in self.name:
            # There are multiple languages, we take the first one
            # It's not the best solution, but it's the simplest
            # FIXME: Choose language set on sale.integration model!
            name = self.name['language'][0]['value']

        return f'{name}  [Code: {self.format_id}, Sku: {self.ref or False}]'

    @property
    def format_sipmle_name(self):
        return f'{self.name or False}  [Code: {self.id}, Sku: {self.ref or False}]'


class TemplateHub:
    """Validate products before import."""

    _schema = ProductTuple._fields

    def __init__(self, product_data_list):
        assert isinstance(product_data_list, list)
        self.products = self._convert_to_namedtuples(product_data_list)

    def __iter__(self):
        for rec in self.products:
            yield rec

    def get_templates(self):
        """Filter and sort products that are templates (no parent_id)"""
        return sorted(filter(lambda x: not x.parent_id, self), key=lambda x: int(x.id))

    def get_variants(self):
        """Filter and sort products that are variants (have parent_id)."""
        return sorted(filter(lambda x: x.parent_id, self), key=lambda x: int(x.id))

    def get_template_ids(self):
        templates = self.get_templates()
        return self._get_ids(templates)

    def get_variant_ids(self):
        variants = self.get_variants()
        return self._get_ids(variants)

    def get_products_with_partial_barcodes(self):
        """Return list of products with part fill barcodes."""
        variants = self._group_by(self.get_variants(), 'parent_id')
        # Find templates where some variants have barcodes but not all
        part_filled_barcode_variants = [
            template_id
            for template_id, variants in variants.items()
            if any(x.barcode for x in variants) and not all(x.barcode for x in variants)
        ]
        products = [x for x in self if x.id in part_filled_barcode_variants]
        return products

    def get_products_with_empty_references(self):
        """Split products into templates and variants based on empty references"""
        templates, variants = self._split_templates_and_variants(
            [x for x in self if not x.ref and not x.skip_ref]
        )
        return templates, variants

    def get_products_with_duplicate_references(self):
        """Return dictionary of products grouped by reference."""
        templates_to_skip_ids = list()
        repeated_ids = self.get_repeated_product_ids()
        products = [x for x in self if x.ref and x.id not in repeated_ids]
        group_dict = self._group_by(products, 'ref', level=2)

        for record_list in group_dict.values():
            templates = [x for x in record_list if not x.parent_id]
            variants = [x for x in record_list if x.parent_id]

            # Skip single templates with only one child variant
            if len(templates) == 1 and len(variants) == 1:
                if variants[0].parent_id == templates[0].id:
                    templates_to_skip_ids.append(templates[0].id)
            # Skip single templates without variants or with multiple variants
            elif len(templates) == 1:
                templates_to_skip_ids.append(templates[0].id)

        # Filter out excluded templates, keep variants
        products = [x for x in products if (x.id not in templates_to_skip_ids) or x.parent_id]
        return self._group_by(products, 'ref', level=2)

    def get_products_with_duplicate_barcodes(self):
        products = [x for x in self if x.barcode]
        return self._group_by(products, 'barcode', level=2)

    def get_products_with_repeated_configurations(self):
        """Return dictionary of repeated configurations grouped by parent record."""
        variants = self.get_variants()
        record_dict = self._group_by(variants, 'id', level=2)
        record_dict_upd = defaultdict(list)

        # Transform variant IDs to actual records and map to their parent templates
        for key, value_list in record_dict.items():
            record = self.find_record_by_id(key)
            record_dict_upd[record] = [
                self.find_record_by_id(x.parent_id) for x in value_list
            ]
        return record_dict_upd

    def get_products_with_nested_configurations(self):
        """Return dictionary of nested configurations grouped by parent record."""
        record_dict = defaultdict(list)
        templates = self.get_templates()
        # Get template IDs that are also used as variants (nested structure)
        template_ids = self._get_ids(filter(lambda x: x.joint_namespace, templates))

        for var in self.get_variants():
            if var.id in template_ids:
                # This variant is also a template, creating nested configuration
                parent = self.find_record_by_id(var.parent_id)
                record_dict[parent].append(var)

        return dict(record_dict)

    def get_repeated_product_ids(self):
        rep_config = self.get_products_with_repeated_configurations()
        return self._get_ids(rep_config.keys())

    def find_record_by_id(self, rec_id):
        for rec in self:
            if rec.id == rec_id:
                return rec
        # This should never happen in normal operation - indicates data inconsistency
        raise ValueError(_('Parent record not found for id: %s') % rec_id)

    @classmethod
    def from_odoo(cls, search_list, reference='default_code', barcode='barcode'):
        """Make class instance from odoo search."""
        def parse_args(rec):
            # Map Odoo product fields to ProductTuple schema
            values = (
                str(rec['id']),
                rec['name'] or '',
                rec.get(barcode) or '',
                rec[reference] or '',
                str(rec['product_tmpl_id'][0]),
                False,  # skip_ref
                True,  # joint_namespace
            )
            return dict(zip(cls._schema, values))
        return cls([parse_args(rec) for rec in search_list])

    @classmethod
    def get_ref_intersection(cls, self_a, self_b):
        """Find references intersection of different instances."""
        def parse_ref(self_):
            return {x.ref for x in self_ if x.ref and not x.skip_ref}

        def filter_records(scope):
            return [x for x in self_a if x.ref in scope], [x for x in self_b if x.ref in scope]

        # Find common references between two TemplateHub instances
        joint_ref = parse_ref(self_a) & parse_ref(self_b)
        records_a, records_b = filter_records(joint_ref)

        return self_a._group_by(records_a, 'ref'), self_b._group_by(records_b, 'ref')

    def _convert_to_namedtuples(self, input_list):
        """Convert to namedtuple for convenient handling."""
        return [self._create_product_tuple(rec) for rec in input_list]

    def _create_product_tuple(self, record):
        args_list = [record[key] for key in self._schema]
        return ProductTuple(*args_list)

    @staticmethod
    def _split_templates_and_variants(records):
        """Split records into templates and variants."""
        templates = [x for x in records if not x.parent_id]
        variants = [x for x in records if x.parent_id]
        return templates, variants

    def _group_by(self, records, attr, level=False):
        """Group records by attribute."""
        dict_ = defaultdict(list)
        [
            [dict_[key].append(x) for x in grouper]
            for key, grouper in groupby(records, key=attrgetter(attr))
        ]

        # If level is provided, return only groups with at least level items
        if level:
            return {
                key: val for key, val in dict_.items() if len(val) >= level
            }
        return dict(dict_)

    def _get_ids(self, records):
        return [str(x.id) for x in records]


PLine = namedtuple('PickingLine', 'external_id qty_demand qty_done is_kit multi_serialization')


class PickingLine(PLine):
    """
    Class for assisting in serializing single stock.move
    during export to an e-commerce API system.
    """

    @property
    def is_done(self):
        return self.qty_demand == self.get_qty()

    def get_qty(self):
        if self.is_kit and self.multi_serialization:
            return self.qty_demand
        return self.qty_done

    def serialize(self):
        return dict(id=self.external_id, qty=self.get_qty())


class PickingSerializer:
    """
    Class for assisting in serializing single stock.picking
    during export to an e-commerce API system.
    """

    def __init__(self, data: dict, lines: List[PickingLine]):
        self._data = data
        self._lines = lines
        self._sequence = None

        self.approved_lines = list()
        self._approve_lines()

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(name)

    def __repr__(self):
        args = (self.erp_id, self._sequence, self.is_backorder, self.is_dropship)
        return '<PickingSerializer: id=%s, sequence=%s, backorder=%s, dropship=%s>' % args

    @property
    def approved(self):
        return bool(self.approved_lines)

    @property
    def kit_ids(self):
        return set([x.external_id for x in self.approved_lines if x.is_kit])

    @property
    def done_ids(self):
        return set([x.external_id for x in self.approved_lines if x.is_done])

    @property
    def pending_ids(self):
        return set([x.external_id for x in self.approved_lines if not x.is_done])

    def serialize(self):
        return dict(
            name=self.name,
            carrier=self.carrier,
            carrier_code=self.carrier_code,
            tracking=self.tracking,
            picking_id=self.erp_id,
            lines=[x.serialize() for x in self.approved_lines],
        )

    def has_components(self):
        return bool(self.kit_ids)

    def pprint(self):
        pprint(self)
        pprint(self._lines)
        pprint(self.approved_lines)

    def _extend_tracking(self, ext_tracking):
        self.tracking = ', '.join(filter(None, [self.tracking, ext_tracking]))

    def _drop_lines(self, ids):
        lines = [x for x in self.approved_lines if x.external_id not in ids]
        self.approved_lines = lines

    def _approve_lines(self):
        """
        Due to kit products, there may be duplicated serialized stock moves
        with the same external_id but different quantities completed.
        Let's group them by external_id and retrieve the one with the highest quantity.
        """
        for __, lines in odoo_groupby(self._lines, key=lambda x: x.external_id):
            sorted_lines = sorted(lines, key=lambda x: x.get_qty())
            self.approved_lines.append(sorted_lines[-1])


class SaleTransferSerializer:
    """
    Class for assisting in serializing stock.picking recordset
    during export to an e-commerce API system.
    """

    def __init__(self, picking_list: List[PickingSerializer]):
        self._pickings = picking_list
        self._initial_setup()

    def __repr__(self):
        return f'<SaleTransferSerializer: picking_ids={[x.erp_id for x in self]}>'

    def __iter__(self):
        for rec in reversed(self._pickings):
            yield rec

    @property
    def transfers(self):
        return sorted(
            filter(lambda x: not x.is_dropship and not x.is_backorder, self),
            key=lambda x: x.erp_id,
        )

    @property
    def backorders(self):
        return sorted(
            filter(lambda x: x.is_backorder and not x.is_dropship, self),
            key=lambda x: x.erp_id,
        )

    @property
    def dropships(self):
        return sorted(
            filter(lambda x: x.is_dropship and not x.is_backorder, self),
            key=lambda x: x.erp_id,
        )

    @property
    def mixed(self):
        return sorted(
            filter(lambda x: x.is_dropship and x.is_backorder, self),
            key=lambda x: x.erp_id,
        )

    def squash(self):
        for picking in self:
            self._drop_duplicated_kit_lines(picking)
            self._drop_duplicated_done_lines(picking)

            if not picking.approved:
                self._reassign_tracking(picking.tracking)

        return self

    def dump(self):
        result = list()

        for picking in self:
            if picking.approved:
                data = picking.serialize()
                result.append(data)

        result.reverse()
        return result

    def pprint(self):
        for picking in self:
            picking.pprint()

    def _initial_setup(self):
        picking_list = self.transfers + self.backorders + self.dropships + self.mixed

        for index, picking in enumerate(picking_list, start=1):
            picking._sequence = index

        self._pickings = picking_list

    def _get_rest(self, sequence):
        return sorted(
            filter(lambda x: x._sequence != sequence, self),
            key=lambda x: x._sequence,
        )

    def _drop_duplicated_kit_lines(self, picking):
        kit_ids = picking.kit_ids
        rest_list = self._get_rest(picking._sequence)

        drop_ids = kit_ids.intersection(set().union(*[x.kit_ids for x in rest_list]))
        picking._drop_lines(drop_ids)

    def _drop_duplicated_done_lines(self, picking):
        pending_ids = picking.pending_ids
        rest_list = self._get_rest(picking._sequence)

        drop_ids = pending_ids.intersection(set().union(*[x.done_ids for x in rest_list]))
        picking._drop_lines(drop_ids)

    def _reassign_tracking(self, tracking):
        pickings = list(filter(lambda x: x.approved, self))
        picking = pickings and pickings[-1]

        if picking:
            picking._extend_tracking(tracking)


class HtmlWrapper:
    """Helper for html wrapping lists and dicts."""

    def __init__(self, integration):
        self.integration = integration
        self.adapter = integration.adapter
        self.base_url = integration.get_base_url_config()
        self.html_list = list()

    @property
    def has_message(self):
        return bool(self.html_list)

    def dump(self):
        return '<br/>'.join(self.html_list)

    def dump_to_file(self, path):
        data = self.dump()
        with open(path, 'w') as f:
            f.write(data)

    def add_title(self, title):
        self._extend_html_list(self._wrap_title(title))

    def add_subtitle(self, title):
        self._extend_html_list(self._wrap_subtitle(title))

    def add_sub_block_for_external_product_list(self, title, id_list):
        title = self._wrap_string(title)
        body = self._wrap_external_product_list(id_list)
        self._extend_html_list(title % body)

    def add_sub_block_for_external_product_dict(self, title, dct, wrap_key=False):
        title = self._wrap_string(title)
        if wrap_key:
            body = self._format_external_product_dict_wrap_key(dct)
        else:
            body = self._format_external_product_dict(dct)
        self._extend_html_list(title % body)

    def add_sub_block_for_internal_template_list(self, title, id_list):
        title = self._wrap_string(title)
        body = self._wrap_internal_template_list(id_list)
        self._extend_html_list(title % body)

    def add_sub_block_for_internal_variant_list(self, title, id_list):
        title = self._wrap_string(title)
        body = self._wrap_internal_variant_list(id_list)
        self._extend_html_list(title % body)

    def add_sub_block_for_internal_template_dict(self, title, dct):
        title = self._wrap_string(title)
        body = self._format_internal_template_dict(dct)
        self._extend_html_list(title % body)

    def add_sub_block_for_internal_variant_dict(self, title, dct):
        title = self._wrap_string(title)
        body = self._format_internal_variant_dict(dct)
        self._extend_html_list(title % body)

    def add_sub_block_for_internal_custom_dict(self, title, dct, model_):
        title = self._wrap_string(title)
        body = self._format_internal_custom_dict(dct, model_)
        self._extend_html_list(title % body)

    def add_sub_block_for_templates_hierarchy(self, template_ids):
        Template = self.integration.env['product.template']
        for tmpl_id in template_ids:
            tmpl = Template.browse(tmpl_id)
            tmpl_link = self.build_internal_link(tmpl_id, Template._name, tmpl.name)
            title = self._wrap_string(tmpl_link)
            body = self._wrap_internal_variant_list_with_name(
                [(f'{tmpl_id}-{x.id}', x.display_name) for x in tmpl.product_variant_ids]
            )
            self._extend_html_list(title % body)

    def build_internal_link(self, id_, model_, name):
        return self._build_internal_link(id_, model_, name)

    def _format_internal_template_dict(self, dct):
        dct_ = self._cut_duplicates(dct)
        return ''.join([
            f'<li>{k}<ul>{self._wrap_internal_template_list(v)}</ul></li>' for k, v in dct_.items()
        ])

    def _format_internal_variant_dict(self, dct):
        dct_ = self._cut_duplicates(dct)
        return ''.join([
            f'<li>{k}<ul>{self._wrap_internal_variant_list(v)}</ul></li>' for k, v in dct_.items()
        ])

    def _format_internal_custom_dict(self, dct, model_):
        dct_ = self._cut_duplicates(dct)
        return ''.join([
            f'<li>{k}<ul>{self._wrap_internal_custom_list(v, model_)}</ul></li>'
            for k, v in dct_.items()
        ])

    def _format_external_product_dict(self, dct):
        dct_ = self._cut_duplicates(dct)
        return ''.join([
            f'<li>{k}<ul>{self._wrap_external_product_list(v)}</ul></li>' for k, v in dct_.items()
        ])

    def _format_external_product_dict_wrap_key(self, dct):
        format_string = str()
        dct_ = self._cut_duplicates(dct)
        for record, value in dct_.items():
            pattern = self.adapter._get_url_pattern(wrap_li=False)
            args = self.adapter._prepare_url_args(record)
            link = pattern % (*args[:-1], record.format_sipmle_name)
            format_string += f'<li>{link}<ul>{self._wrap_external_product_list(value)}</ul></li>'
        return format_string

    def _wrap_internal_template_list(self, id_list):
        return self._convert_to_html('product.template', id_list)

    def _wrap_internal_variant_list_with_name(self, id_list_name):
        return self._convert_to_html_with_name('product.product', id_list_name)

    def _wrap_internal_variant_list(self, id_list):
        return self._convert_to_html('product.product', id_list)

    def _wrap_internal_custom_list(self, id_list, model_):
        return self._convert_to_html(model_, id_list)

    def _wrap_external_product_list(self, id_list):
        return self.adapter._convert_to_html(id_list)

    @staticmethod
    def _wrap_string(title):
        return f'<div><strong>{title}</strong><ul>%s</ul></div>'

    @staticmethod
    def _wrap_title(title):
        return f'<div><strong>{title}</strong></div>'

    @staticmethod
    def _wrap_subtitle(title):
        return f'<div>{title}</div>'

    @staticmethod
    def _cut_duplicates(dct):
        def are_product_tuples_equal(pt1, pt2):
            return all(getattr(pt1, field) == getattr(pt2, field) for field in pt1._fields)

        result = dict()
        for key, value in dct.items():
            result[key] = list()
            for record in value:
                if not any(are_product_tuples_equal(record, x) for x in result[key]):
                    result[key].append(record)

        return result

    @staticmethod
    def _internal_pattern():
        return '<a href="%s/web#id=%s&model=%s&view_type=form" target="_blank">%s</a>'

    def _extend_html_list(self, html_text):
        self.html_list.append(html_text)

    def _convert_to_html(self, model_, id_list):
        arg_list = ((x.id, model_, x.format_name) for x in id_list)
        links = (self._build_internal_link(*args) for args in arg_list)
        return ''.join([f'<li>{link}</li>' for link in links])

    def _convert_to_html_with_name(self, model_, id_list_name):
        # It seems this method was added for the certain Customer.
        # Let's further use splitting complex ID 'x.split('-')[-1]'
        arg_list = ((x.split('-')[-1], model_, n) for x, n in id_list_name)
        links = (self._build_internal_link(*args) for args in arg_list)
        return ''.join([f'<li>{link}</li>' for link in links])

    def _build_internal_link(self, id_, model_, name):
        pattern = self._internal_pattern()
        return pattern % (self.base_url, id_, model_, name)


class MeasureTime:
    def __init__(self, description=None):
        self.description = description

        # Set up a dedicated logger for the execution time
        self.logger = logging.getLogger('execution_time_logger')
        self.logger.setLevel(logging.INFO)

        # Make sure we don't propagate to root logger or any other logger
        self.logger.propagate = False

        # Create a file handler to log to a specific file
        file_handler = logging.FileHandler('/tmp/execution_times.log')
        file_handler.setFormatter(logging.Formatter('%(message)s'))

        # Clear existing handlers and add the new file handler
        self.logger.handlers = []
        self.logger.addHandler(file_handler)

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.end = time.time()
        self.interval = self.end - self.start
        if self.description:
            self.logger.info(
                f'[{self.description}] Code block executed in: {self.interval:.4f} seconds')
        else:
            self.logger.info(f'Code block executed in: {self.interval:.4f} seconds')


class MergeableDict:

    def __init__(self):
        self._dict = {}

    def dump(self):
        return self._dict

    def merge(self, **kw):
        """
        Merge the given keyword arguments into the current data.
        If the key already exists, the value is merged with the existing value.
        If the value is a list, the new values are appended to the existing list.
        If the value is a dict, the new values are merged with the existing dict.
        """

        for key, value in kw.items():
            if key in self._dict:
                nested_data = self._dict[key]

                if isinstance(nested_data, list):
                    nested_data.extend(value)
                elif isinstance(nested_data, dict):
                    nested_data.update(value)
                else:
                    self._dict[key] = value
            else:
                self._dict[key] = value


class ExtractNode:

    class MissedValue:
        pass

    def __init__(self, key_string: str, return_type, raise_error: bool = False):
        self.keys = key_string.split('.')
        self._type = return_type
        self._raise_error = raise_error

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            if isinstance(result, str):
                result = json.loads(result)

            data = self._extract(result, self.keys)

            if isinstance(data, ExtractNode.MissedValue):
                if self._raise_error:
                    raise ErrorStore.JsonMissedKey(
                        'ExtractNode parse error: Key "%s" not found' % ('.'.join(self.keys))
                    )

                return self.get_default()

            return data

        return wrapper

    def _extract(self, data, key_list):
        """
        Recursively extract the value based on the provided key list
        """
        if not key_list:
            # No more keys to process, return the current data
            return data

        key, *remaining_keys = deepcopy(key_list)

        if isinstance(data, list):
            if key.isdigit():
                if int(key) < len(data):
                    # If the key is an integer and within the list bounds, continue extraction
                    return self._extract(data[int(key)], remaining_keys)

                _logger.warning('Integration-data parse error: Index "%s" out of range', key)
                return ExtractNode.MissedValue()

            # Handle the all lists elements
            return list(filter(
                lambda x: not isinstance(x, ExtractNode.MissedValue),
                [self._extract(x, key_list) for x in data],
            ))

        if isinstance(data, dict):
            if key in data:
                return self._extract(data[key], remaining_keys)

            _logger.warning('Integration-data parse error: Key "%s" not found', key)
            return ExtractNode.MissedValue()

        # Unknown data type (neither a list nor a dictionary)_extract
        _logger.warning(
            'Integration-data parse error: Expected list or dict at key "%s", got %s', key, type(data).__name__
        )
        return ExtractNode.MissedValue()

    def get_default(self):
        return self._type() if callable(self._type) else self._type

    @classmethod
    def extract_raw(
        cls,
        json_data : Union[str, Dict, List],
        key_string: str,
        return_type: Type,
        raise_error: bool = False,
    ):
        # 1. init instance
        # 2. invoke the __call__ method
        # 3. invoke the `wrapper` function returned from the step 2
        return cls(key_string, return_type, raise_error)(lambda: json_data)()


def run_preprocessing_script(script: str, context: dict, raise_error: bool = False) -> str:
    """
    Executes the preprocessing script in a controlled environment.
    """
    try:
        safe_eval(script.strip(), context=context, mode='exec')
    except Exception as e:
        if raise_error:
            raise
        _logger.warning('Preprocess script execution failed: %s', e)
        return ''

    try:
        return context['value']
    except (TypeError, ValueError) as e:
        if raise_error:
            raise
        _logger.warning('Failed to serialize value in preprocess script: %s', e)
        return ''


def expose_for_testing(label):
    """
    Decorator to mark methods as debuggable with a user-friendly name.

    Args:
        label (str): User-friendly name to display in the selection field

    Usage:
        @expose_for_testing('Import Order by ID')
        def integrationApiReceiveOrder(self):
            # method implementation
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._expose_for_testing = True
        wrapper._testing_label = label

        return wrapper

    return decorator


def _get_retry_timeout(ex: Exception, attempt: int, is_client: bool = True) -> int:
    default_timeout = CLIENT_TIMEOUT if is_client else SERVER_TIMEOUT
    retry_after = getattr(ex, 'retry_after', None)
    return retry_after or default_timeout * attempt


def _format_retry_exception(ex: Exception, attempt: int, wait: int, method_name: str, is_client: bool = True) -> str:
    """Format exception message for logging."""
    return 'Integration %s (%s); %s-attempt %s --> wait %s: %s' % (
        ex.__class__.__name__,
        ex.args[0] if ex.args else str(ex),
        'Client' if is_client else 'Server',
        attempt,
        wait,
        method_name,
    )


def catch_exception(method):
    @wraps(method)
    def _catch_exception(*args, _client_attempt=1, _server_attempt=1, **kwargs):
        retry = partial(_catch_exception, *args, **kwargs)

        try:
            result = method(*args, **kwargs)
        except (
            ErrorStore.SSLError,
            ErrorStore.RequestsConnectionError,
            ErrorStore.ResourceConflict,
            ErrorStore.TooManyRequestsError,
        ) as ex:
            if _client_attempt <= CLIENT_LIMIT:
                wait = _get_retry_timeout(ex, _client_attempt)
                _logger.warning(_format_retry_exception(ex, _client_attempt, wait, method.__name__, is_client=True))
                sleep(wait)
                return retry(_client_attempt=_client_attempt + 1)
            raise ex

        except ErrorStore.ServerError as ex:
            if _server_attempt <= SERVER_LIMIT:
                wait = _get_retry_timeout(ex, _server_attempt, is_client=False)
                _logger.warning(_format_retry_exception(ex, _server_attempt, wait, method.__name__, is_client=False))
                sleep(wait)
                return retry(_server_attempt=_server_attempt + 1)
            raise ex

        return result

    return _catch_exception
