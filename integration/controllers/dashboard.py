#  See LICENSE file for full copyright and licensing details.

import re
from time import time
from datetime import datetime, timedelta
from functools import wraps

from odoo import _
from odoo.http import Controller, route, request
from odoo.exceptions import ValidationError

from ..wizard.integration_dashboard_cache import (
    SALE_CARDS_TYPE,
    SALE_DATA_TYPE,
    TOP_PRODUCTS_TYPE,
    STORE_PERFORMANCE_TYPE,
)


DATE_FORMAT = '%Y-%m-%d'
DATE_PATTERN_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

KEY_TITLE_MAPPING = {
    'sales_revenue': 'Total Sales Revenue',
    'number_of_orders': 'Number of Orders',
    'average_order_value': 'Average / Median Order Value',
    'repeat_purchase_rate': 'Repeat Purchase Rate',
}


def get_timestamp_key() -> str:
    return str(int(time()))


def prepare_cache_tag(start: str, end: str, integration_ids: list) -> str:
    return f'{start}_{end}_{"-".join(str(x) for x in integration_ids)}'


def is_one_hour_timedelta(current_timestamp: str, previous_timestamp: str) -> bool:
    return (int(current_timestamp) - int(previous_timestamp)) <= 3600


def validate_integration_dashboard_args(start_date, end_date, integration_ids):
    """
    Assumptions:
        - start_date and end_date are strings in 'YYYY-MM-DD' format.
        - integration_ids is a list of integration IDs.
    """
    if not (
        isinstance(start_date, str) and DATE_PATTERN_RE.match(start_date)
        and isinstance(end_date, str) and DATE_PATTERN_RE.match(end_date)
        and isinstance(integration_ids, list) and integration_ids
    ):
        raise ValidationError(
            _('Incorrect dashboard arguments: start_date=%s, end_date=%s, integration_ids=%s')
            % (start_date, end_date, integration_ids)
        )


def cached(func):

    @wraps(func)
    def wrapper(self_, *args, **kw):
        _args = kw.get('start_date'), kw.get('end_date'), kw.get('integration_ids')
        validate_integration_dashboard_args(*_args)

        tag = prepare_cache_tag(*_args)
        timestamp = get_timestamp_key()
        ttype = request.httprequest.path.rsplit('/', 1)[-1]

        if not kw.get('force_refresh'):
            cache_data = request.env['integration.dashboard.cache'].get_last_record(ttype, tag)

            if cache_data and is_one_hour_timedelta(timestamp, cache_data['timestamp']):
                return cache_data['data']

        result = func(self_, *_args)

        request.env['integration.dashboard.cache'].create({
            'tag': tag,
            'ttype': ttype,
            'timestamp': timestamp,
            'data': result,
        })

        return result

    return wrapper


class DashboardController(Controller):

    @route('/integration-dashboard/get-active-integrations', type='json', auth='user')
    def integration_dashboard_get_active_integrations(self) -> list:
        return request.env['sale.integration'].get_active_integrations()

    @route(f'/integration-dashboard/{SALE_CARDS_TYPE}', type='json', auth='user')
    @cached
    def integration_dashboard_get_sales_cards(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
        **kw,
    ) -> list:

        # 1. Parse dates
        start_dt = datetime.strptime(start_date, DATE_FORMAT)
        end_dt = datetime.strptime(end_date, DATE_FORMAT)
        # Current period length
        period_length = end_dt - start_dt
        # Previous period: same length, ending right before start_dt
        previous_end_dt = start_dt
        previous_start_dt = start_dt - period_length

        previous_start = previous_start_dt.strftime(DATE_FORMAT)
        previous_end = (previous_end_dt - timedelta(days=1)).strftime(DATE_FORMAT)

        # 2. Fetch data
        SaleOrder = request.env['sale.order']

        current_data = SaleOrder._integration_dashboard_get_sales_cards(start_date, end_date, integration_ids)
        previous_data = SaleOrder._integration_dashboard_get_sales_cards(previous_start, previous_end, integration_ids)

        def compute_up_percent(key):
            current_val = current_data[key]
            prev_val = previous_data[key]

            if int(prev_val) == 0:
                # Not enough data
                return None

            return round(((current_val - prev_val) / prev_val) * 100, 2)

        # 3. Serialize data
        data = []

        for key, value in current_data.items():
            if key in ('currency_symbol', 'median_order_value'):
                continue
            elif key == 'average_order_value':
                value = {
                    'average': value,
                    'median': current_data['median_order_value']
                }

            data.append({
                'title': KEY_TITLE_MAPPING.get(key, key),
                'value': value,
                'percent': compute_up_percent(key),
                'currency_symbol': current_data['currency_symbol'],
            })

        return data

    @route(f'/integration-dashboard/{SALE_DATA_TYPE}', type='json', auth='user')
    @cached
    def integration_dashboard_get_sales_data(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
        **kw,
    ) -> dict:

        SaleOrder = request.env['sale.order']
        args = start_date, end_date, integration_ids

        sales_over_time_data = SaleOrder._integration_dashboard_get_sales_data(*args)
        order_value_distribution_data = SaleOrder._integration_dashboard_get_order_value_distribution(*args)

        data = dict()

        if sales_over_time_data:
            data['sales_over_time'] = sales_over_time_data

        if order_value_distribution_data:
            data['order_value_distribution'] = order_value_distribution_data

        return data

    @route(f'/integration-dashboard/{TOP_PRODUCTS_TYPE}', type='json', auth='user')
    @cached
    def integration_dashboard_get_top_products(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
        **kw,
    ) -> dict:

        products_data = request.env['sale.order']._integration_dashboard_get_products_data(
            start_date,
            end_date,
            integration_ids,
        )

        return {'products': products_data} if products_data else {}

    @route(f'/integration-dashboard/{STORE_PERFORMANCE_TYPE}', type='json', auth='user')
    @cached
    def integration_dashboard_get_store_performance(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
        **kw,
    ) -> dict:

        SaleOrder = request.env['sale.order']
        args = start_date, end_date, integration_ids

        stores_data = SaleOrder._integration_dashboard_get_store_performance(*args)
        countries_data = SaleOrder._integration_dashboard_get_top_countries(*args)
        customers_data = SaleOrder._integration_dashboard_get_new_vs_returning_customers(*args)

        data = dict()

        if stores_data:
            data['stores'] = stores_data

        if countries_data:
            data['countries'] = countries_data

        if customers_data:
            data['customers'] = customers_data

        return data
