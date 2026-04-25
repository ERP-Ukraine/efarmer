# See LICENSE file for full copyright and licensing details.

import json
from copy import deepcopy

from odoo import api, models, fields


class ExternalIntegrationCatalog(models.Model):
    _name = 'integration.catalog.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Catalog External'

    status = fields.Selection(
        string='Status',
        selection=[
            ('ACTIVE', 'Active'),
            ('ARCHIVED', 'Archived'),
            ('DRAFT', 'Draft'),
        ],
        required=True,
    )

    catalog_type = fields.Selection(
        string='Catalog Type',
        selection=[
            ('MARKET', 'Market Catalog'),
            ('COMPANY_LOCATION', 'Company Location Catalog'),
            ('APP', 'App Catalog'),
        ],
        required=True,
    )

    pricelist_data = fields.Char(
        string='Pricelist Data',
        help='Pricelist data from external system',
    )

    publication_data = fields.Char(
        string='Publication Data',
        help='Publication data from external system',
    )

    currency_code = fields.Char(
        string='Currency Code',
        compute='_compute_from_pricelist_data',
        help='Currency code from external system',
        store=True,
    )

    market_data = fields.Char(
        string='Market Data',
        help='Catalog market data from external system',
    )

    markets = fields.Char(
        string='Markets',
        help='Markets from external system',
        compute='_compute_from_market_data',
        store=True,
    )

    company_location_catalogs = fields.Char(
        string='Company Location Catalogs',
        help='Company Location Catalogs from external system',
        compute='_compute_from_market_data',
        store=True,
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.name} ({rec.currency_code})'

    @property
    def is_market_catalog(self):
        return self.catalog_type == 'MARKET'

    @property
    def is_company_location_catalog(self):
        return self.catalog_type == 'COMPANY_LOCATION'

    @property
    def is_app_catalog(self):
        return self.catalog_type == 'APP'

    @property
    def market_data_dict(self):
        data = self.market_data
        if data:
            return json.loads(data)
        return {}

    @property
    def pricelist_data_dict(self):
        data = self.pricelist_data
        if data:
            return json.loads(data)
        return {}

    @property
    def publication_data_dict(self):
        data = self.publication_data
        if data:
            return json.loads(data)
        return {}

    @api.depends('pricelist_data')
    def _compute_from_pricelist_data(self):
        for rec in self:
            rec.currency_code = rec.pricelist_data_dict.get('currency')

    @api.depends('market_data')
    def _compute_from_market_data(self):
        for rec in self:
            markets_ = locations_ = False
            market_data_dict = rec.market_data_dict

            if market_data_dict:
                if rec.is_market_catalog:
                    markets_ = ', '.join([x['name'] for x in (market_data_dict.get('markets') or [])])
                elif rec.is_company_location_catalog:
                    locations_ = ', '.join([x['name'] for x in (market_data_dict.get('company_locations') or [])])

            rec.markets = markets_
            rec.company_location_catalogs = locations_

    def create_or_update(self, integration_id: int, data: dict) -> 'models.Model':
        data_ = deepcopy(data)

        pricelist_data = json.dumps(data_.pop('pricelist_data', {}))
        publication_data = json.dumps(data_.pop('publication_data', {}))
        market_data = json.dumps(data_.pop('market_data', {}))

        values = {
            **data_,
            'integration_id': integration_id,
            'pricelist_data': pricelist_data,
            'publication_data': publication_data,
            'market_data': market_data,
        }

        catalog = self.search([
            ('code', '=', values['code']),
            ('integration_id', '=', integration_id),
        ])

        if catalog:
            catalog.write(values)
        else:
            catalog = self.create(values)

        return catalog
