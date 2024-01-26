# See LICENSE file for full copyright and licensing details.

import base64
import logging
import os
import io
import time
import re

from PIL import Image, UnidentifiedImageError

from collections import defaultdict, namedtuple
from functools import wraps
from itertools import groupby
from operator import attrgetter
from pprint import pprint
from psycopg2 import OperationalError
from decimal import Decimal, ROUND_HALF_UP

from odoo import _
from odoo.exceptions import ValidationError
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.misc import groupby as odoo_groupby

from odoo.addons.queue_job.exception import RetryableJobError


_logger = logging.getLogger(__name__)


IS_TRUE = '1'
IS_FALSE = '0'


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


def not_implemented(method):
    def wrapper(self, *args, **kw):
        raise ValidationError(_(
            '[Debug] This feature is still not implemented (%s.%s()).'
            % (self.__class__.__name__, method.__name__)
        ))
    return wrapper


def raise_requeue_job_on_concurrent_update(method):
    @wraps(method)
    def wrapper(self, *args, **kw):
        try:
            result = method(self, *args, **kw)
            # flush() is needed to push all the pending updates to the database
            self.env["base"].flush()
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


def escape_trash(value, allowed_chars=None, max_length=None):
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

    return value


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


class Adapter:
    """Class wrapper for Integration API-Client."""

    def __init__(self, adapter_core, integration):
        self.__cache_core = adapter_core
        self._env = integration.env

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


def make_list_if_not(value):
    if not isinstance(value, list):
        value = [value]

    return value


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
        return f'{self.name or False}  [Code: {self.format_id}, Sku: {self.ref or False}]'

    @property
    def format_sipmle_name(self):
        return f'{self.name or False}  [Code: {self.id}, Sku: {self.ref or False}]'


class TemplateHub:
    """Validate products before import."""

    _schema = ProductTuple._fields

    def __init__(self, input_list):
        assert type(input_list) == list
        self.product_list = self._convert_to_clean(input_list)

    def __iter__(self):
        for rec in self.product_list:
            yield rec

    def get_templates(self):
        return sorted(filter(lambda x: not x.parent_id, self), key=lambda x: int(x.id))

    def get_variants(self):
        return sorted(filter(lambda x: x.parent_id, self), key=lambda x: int(x.id))

    def get_template_ids(self):
        templates = self.get_templates()
        return self._get_ids(templates)

    def get_variant_ids(self):
        variants = self.get_variants()
        return self._get_ids(variants)

    def get_part_fill_barcodes(self):
        variants = self._group_by(self.get_variants(), 'parent_id')
        part_fill_variants = [
            template_id
            for template_id, variants in variants.items()
            if any(x.barcode for x in variants) and not all(x.barcode for x in variants)
        ]
        products = [x for x in self if x.id in part_fill_variants]
        return products

    def get_empty_ref_ids(self):
        templates, variants = self._split_products(
            [x for x in self if not x.ref and not x.skip_ref]
        )
        return templates, variants

    def get_dupl_refs(self):
        skip_ids = list()
        repeated_ids = self.get_repeated_ids()
        products = [x for x in self if x.ref and x.id not in repeated_ids]
        group_dict = self._group_by(products, 'ref', level=2)

        for record_list in group_dict.values():
            templates = [x for x in record_list if not x.parent_id]
            variants = [x for x in record_list if x.parent_id]

            if len(templates) == 1 and len(variants) == 1:
                template = templates[0]
                variant = variants[0]
                if variant.parent_id == template.id:
                    skip_ids.append(template.id)
            elif len(templates) == 1 and len(variants) > 1:
                template = templates[0]
                skip_ids.append(template.id)

        products = [x for x in products if x.id not in skip_ids]
        return self._group_by(products, 'ref', level=2)

    def get_tmpl_dupl_refs(self):
        skip_ids = self.get_repeated_ids()
        products = [x for x in self if all([x.ref, not x.parent_id, x.id not in skip_ids])]
        return self._group_by(products, 'ref', level=2)

    def get_var_dupl_refs(self):
        skip_ids = self.get_repeated_ids()
        products = [x for x in self if all([x.ref, x.parent_id, x.id not in skip_ids])]
        return self._group_by(products, 'ref', level=2)

    def get_dupl_barcodes(self):
        products = [x for x in self if x.barcode]
        return self._group_by(products, 'barcode', level=2)

    def get_repeated_configurations(self):
        variants = self.get_variants()
        record_dict = self._group_by(variants, 'id', level=2)
        record_dict_upd = defaultdict(list)

        for key, value_list in record_dict.items():
            record = self.find_record_by_id(key)
            record_dict_upd[record] = [
                self.find_record_by_id(x.parent_id) for x in value_list
            ]
        return record_dict_upd

    def get_nested_configurations(self):
        record_dict = defaultdict(list)
        templates = self.get_templates()
        template_ids = self._get_ids(filter(lambda x: x.joint_namespace, templates))

        for var in self.get_variants():
            if var.id in template_ids:
                parent = self.find_record_by_id(var.parent_id)
                record_dict[parent].append(var)

        return dict(record_dict)

    def get_repeated_ids(self):
        rep_config = self.get_repeated_configurations()
        return self._get_ids(rep_config.keys())

    def find_record_by_id(self, rec_id):
        for rec in self:
            if rec.id == rec_id:
                return rec
        # In my opinion there is no way not to find the required record
        assert 1 == 0, 'Parent record not found'

    @classmethod
    def from_odoo(cls, search_list, reference='default_code', barcode='barcode'):
        """Make class instance from odoo search."""
        def parse_args(rec):
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

        joint_ref = parse_ref(self_a) & parse_ref(self_b)
        records_a, records_b = filter_records(joint_ref)

        return self_a._group_by(records_a, 'ref'), self_b._group_by(records_b, 'ref')

    def _convert_to_clean(self, input_list):
        """Convert to namedtuple for convenient handling."""
        return [self._serialize_by_scheme(rec) for rec in input_list]

    def _serialize_by_scheme(self, record):
        args_list = [record[key] for key in self._schema]
        return ProductTuple(*args_list)

    @staticmethod
    def _split_products(records):
        templates = [x for x in records if not x.parent_id]
        variants = [x for x in records if x.parent_id]
        return templates, variants

    def _group_by(self, records, attr, level=False):
        dict_ = defaultdict(list)
        [
            [dict_[key].append(x) for x in grouper]
            for key, grouper in groupby(records, key=attrgetter(attr))
        ]
        if level:
            return {
                key: val for key, val in dict_.items() if len(val) >= level
            }
        return dict(dict_)

    def _get_ids(self, records):
        return [str(x.id) for x in records]


PLine = namedtuple('PickingLine', 'external_id qty_demand qty_done is_kit')


class PickingLine(PLine):
    """
    Class for assisting in serializing single stock.move
    during export to an e-commerce API system.
    """

    @property
    def is_done(self):
        return self.qty_demand == self.get_qty()

    def get_qty(self):
        if self.is_kit:
            return self.qty_demand
        return self.qty_done

    def serialize(self):
        return dict(id=self.external_id, qty=self.get_qty())


class PickingSerializer:
    """
    Class for assisting in serializing single stock.picking
    during export to an e-commerce API system.
    """

    def __init__(self, name, carrier, tracking, lines, erp_id, is_backorder, is_dropship):
        self.name = name
        self.carrier = carrier
        self.tracking = tracking
        self.approved_lines = list()

        self._lines = lines

        self._erp_id = erp_id
        self._is_backorder = is_backorder
        self._is_dropship = is_dropship
        self._sequence = None

        self._approve_lines()

    def __repr__(self):
        args = (self.erp_id, self.sequence, self.is_backorder, self.is_dropship)
        return '<PickingSerializer: id=%s, sequence=%s, backorder=%s, dropship=%s>' % args

    @property
    def approved(self):
        return bool(self.approved_lines)

    @property
    def is_empty(self):
        return not self.approved

    @property
    def erp_id(self):
        return self._erp_id

    @property
    def is_backorder(self):
        return self._is_backorder

    @property
    def is_dropship(self):
        return self._is_dropship

    @property
    def sequence(self):
        return self._sequence

    @sequence.setter
    def sequence(self, value):
        self._sequence = value

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
        data = dict(
            name=self.name,
            carrier=self.carrier,
            tracking=self.tracking,
            lines=[x.serialize() for x in self.approved_lines],
        )
        return data

    def pprint(self):
        pprint(self)
        pprint(self._lines)
        pprint(self.approved_lines)

    def _extend_tracking(self, ext_tracking):
        values = [self.tracking, ext_tracking]
        self.tracking = ', '.join(filter(None, values))

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

    def __init__(self, picking_list):
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

            if picking.is_empty:
                self._reassign_tracking(picking.tracking)

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
            picking.sequence = index

        self._pickings = picking_list

    def _get_rest(self, sequence):
        return sorted(
            filter(lambda x: x.sequence != sequence, self),
            key=lambda x: x.sequence,
        )

    def _drop_duplicated_kit_lines(self, picking):
        kit_ids = picking.kit_ids
        rest_list = self._get_rest(picking.sequence)

        drop_ids = kit_ids.intersection(set().union(*[x.kit_ids for x in rest_list]))
        picking._drop_lines(drop_ids)

    def _drop_duplicated_done_lines(self, picking):
        pending_ids = picking.pending_ids
        rest_list = self._get_rest(picking.sequence)

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
        self.adapter = integration._build_adapter()
        self.base_url = integration.sudo().env['ir.config_parameter'].get_param('web.base.url')
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
        return f'<div>{title}<ul>%s</ul></div>'

    @staticmethod
    def _wrap_title(title):
        return f'<div><strong>{title}</strong><hr/></div>'

    @staticmethod
    def _wrap_subtitle(title):
        return f'<div>{title}<hr/></div>'

    @staticmethod
    def _cut_duplicates(dct):
        return {k: list(set(v)) for k, v in dct.items()}

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
