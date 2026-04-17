#  See LICENSE file for full copyright and licensing details.

import re
from typing import Union
from urllib.parse import urlparse

from odoo import _
from odoo.exceptions import ValidationError


INT_PATTERN = re.compile(r'\d+')


def parse_int(value_str: str, index) -> int:
    if not isinstance(value_str, str) or not value_str:
        return 0

    match = re.findall(INT_PATTERN, value_str)

    try:
        return int(match[index])
    except (IndexError, ValueError):
        return 0


def parse_graphql_id(graphql_id: str) -> str:
    """
    Parse the ID from a Shopify GraphQL ID.
    """
    return graphql_id.rsplit('/', 1)[-1] if graphql_id else ''


class CheckScope:
    """Check Shopify API access scope."""

    def __init__(self, *scopes):
        self.scope_list = scopes

    def __call__(self, method):
        def scope_checker(instance, *args, **kw):
            for scope in self.scope_list:
                if scope not in instance.access_scopes:
                    raise ValidationError(_(
                        'The Shopify API scope "%s" is not permitted for your app.\n\n'
                        'Please update your app permissions in the Shopify Admin panel to include this scope.\n'
                        'To do this, go to: Settings → Apps and sales channels → Develop apps → [Your App] → '
                        'Configuration → Admin API integration → Edit, enable the missing permission, and save changes.\n\n'  # noqa: E501
                        'After that, return to Odoo and click the "Refresh" button in the Quick Configuration wizard.\n\n'  # noqa: E501
                        'For a detailed step-by-step guide, see our article:\n'
                        'https://ecosystem.ventor.tech/faq/e-commerce-connectors/shopify/placeholder-for-how-to-fix-missing-permissions-for-the-shopify-connector/'  # noqa: E501
                    ) % scope)

            return method(instance, *args, **kw)
        return scope_checker


def parse_gql_json(data: Union[dict, list]) -> Union[dict, list]:
    if isinstance(data, list):
        return [parse_gql_json(x) for x in data]

    if not isinstance(data, dict):
        return data

    if 'edges' in data:
        return [parse_gql_json(x) for x in data['edges']]

    if 'nodes' in data:
        return [parse_gql_json(x) for x in data['nodes']]

    if 'node' in data:
        return parse_gql_json(data['node'])

    for key, value in data.items():
        data[key] = parse_gql_json(value)

    return data


def prettify_gql_query(string_: str, indent: int = 4) -> str:
    string_ = string_.translate(str.maketrans('\n\r\t', '   ')).strip()
    string_ = re.sub(r'[{(]\s+', lambda m: m.group(0)[0], re.sub(r'\s+[})]', lambda m: m.group(0)[-1], string_))
    string_ = re.sub(r'\s+', ' ', string_)

    result = []
    complexity = 0
    previous_value = ''

    for char in string_:
        value = char

        if char == '{':
            complexity += 1
            value = '{\n' + ' ' * (complexity * indent)

            if previous_value and (previous_value.isalpha() or previous_value.isdigit() or previous_value == ')'):
                value = f' {value}'
            previous_value = char
        elif char == '}':
            complexity -= 1
            value = '\n' + ' ' * (complexity * indent) + '}'
            previous_value = char
        elif char.isalpha():
            if previous_value == ' ':
                value = '\n' + ' ' * (complexity * indent) + char
                previous_value = char
        else:
            if previous_value == ',':
                pass
            else:
                previous_value = char

        result.append(value)

    return ''.join(result)


def lists_are_equal(list1: list, list2: list) -> bool:
    # Convert dicts to frozensets of items for hashability
    return {frozenset(d.items()) for d in list1} == {frozenset(d.items()) for d in list2}


def loggify_request_payload(value, limit: int = None) -> str:
    if isinstance(value, dict):
        str_ = '; '.join(f'{k}: {v}' for k, v in value.items())
    else:
        str_ = value

    value_ = re.sub(r'\s+', ' ', str_)

    if limit:
        value_ = value_[:limit] + '...'

    return value_


def prepare_shopify_url(url):  # Based on python-shopify lib
    if not url or (url.strip() == ''):
        return None

    url = re.sub('^https?://', '', url)
    shop = urlparse('https://' + url).hostname

    if shop is None:
        return None

    idx = shop.find('.')
    if idx != -1:
        shop = shop[0:idx]

    if len(shop) == 0:
        return None

    return f'{shop}.myshopify.com'
