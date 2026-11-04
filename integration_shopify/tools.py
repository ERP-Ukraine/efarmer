#  See LICENSE file for full copyright and licensing details.

import hmac
import re
from hashlib import sha256
from typing import Union
from urllib.parse import urlparse

from odoo import _
from odoo.exceptions import ValidationError


INT_PATTERN = re.compile(r'\d+')
SHOP_DOMAIN_PATTERN = re.compile(r'[a-z0-9][a-z0-9\-]*\.myshopify\.com')

# TODO: placeholder — the support article has not been published yet.
MISSING_SCOPES_ARTICLE_URL = (
    'https://ecosystem.ventor.tech/faq/e-commerce-connectors/shopify/'
    'placeholder-for-how-to-fix-missing-permissions-for-the-shopify-connector/'
)


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
                        'The scope "%s" is not permitted in the private app of your store. '
                        'Change it in the "Admin API" settings.' % scope
                    ))

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


def is_valid_shop_domain(shop) -> bool:
    """
    Check that the value is a plain `<store>.myshopify.com` hostname, the only form Shopify sends in the OAuth callback.
    """
    return isinstance(shop, str) and bool(SHOP_DOMAIN_PATTERN.fullmatch(shop))


def compute_oauth_hmac(params: dict, secret: str) -> str:
    """
    Compute the signature Shopify puts into the `hmac` parameter of the OAuth callback.

    The `hmac` parameter itself is left out, the rest is sorted and signed with HMAC-SHA256 using the app's client
    secret. The delimiters inside keys and values are escaped the same way python-shopify does it.
    Reference: https://shopify.dev/docs/apps/build/authentication-authorization/authenticate-standalone-apps

    :param params: query parameters of the callback request
    :param secret: client secret of the Shopify app
    :return: hex digest
    """
    pairs = []
    for key, value in params.items():
        if key == 'hmac':
            continue

        key = str(key).replace('%', '%25').replace('=', '%3D')
        value = str(value).replace('%', '%25')
        pairs.append(f'{key}={value}'.replace('&', '%26'))

    message = '&'.join(sorted(pairs))

    return hmac.new(secret.encode('utf-8'), message.encode('utf-8'), sha256).hexdigest()
