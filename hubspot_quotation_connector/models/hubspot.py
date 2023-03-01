# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

from typing import List
from hubspot import HubSpot
from hubspot.crm.deals.models import SimplePublicObject
from hubspot.crm.contacts import (
    PublicObjectSearchRequest as ContactSearchRequest,
    Filter as ContactFilter,
    FilterGroup as ContactFilterGroup,
)
from hubspot.crm.deals import (
    PublicObjectSearchRequest as DealsSearchRequest,
    Filter as DealsFilter,
    FilterGroup as DealsFilterGroup,
)
from odoo import fields, models
from odoo.tools.cache import ormcache


class HubSpotConfig(models.Model):
    _name = 'hubspot.config'
    _description = 'HubSpot Configuration'

    name = fields.Char(required=True)
    access_token = fields.Char(required=True)

    @property
    @ormcache('self.env.uid', 'self.access_token')
    def _client(self):
        """
        HubSpot Client
        :rtype: HubSpot
        """
        self.ensure_one()
        return HubSpot(access_token=self.access_token)

    def get_deals_by_partner(
            self,
            partner_id: 'odoo.model.res_partner',
            limit: int = 1
    ) -> List[SimplePublicObject]:
        contact_items = self.get_contact_by_email(partner_id.email)
        if not contact_items:
            return []
        response = self._client.crm.deals.search_api.do_search(
            public_object_search_request=DealsSearchRequest(
                filter_groups=[
                    DealsFilterGroup(
                        filters=[
                            DealsFilter(
                                property_name='associations.contact',
                                operator='IN',
                                values=[item.id for item in contact_items],
                            )
                        ]
                    ),
                ],
                limit=limit,
            )
        )
        return response.results

    def get_contact_by_email(self, email: str, limit=1) -> List[SimplePublicObject]:
        response = self._client.crm.contacts.search_api.do_search(
            ContactSearchRequest(
                filter_groups=[
                    ContactFilterGroup(
                        filters=[
                            ContactFilter(
                                operator='EQ',
                                property_name='email',
                                value=email
                            )
                        ]
                    )
                ],
                limit=limit,
            )
        )
        return response.results
