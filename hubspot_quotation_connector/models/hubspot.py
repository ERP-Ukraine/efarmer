# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

from typing import List, Dict, Union, Any
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
    SimplePublicObjectInput as DealInput,
)
from datetime import datetime, date

from odoo import fields, models, _, api
from odoo.tools.cache import ormcache
from odoo.tools.safe_eval import safe_eval


class HubSpotConfig(models.Model):
    _name = "hubspot.config"
    _description = "HubSpot Configuration"

    name = fields.Char(required=True)
    access_token = fields.Char(required=True)

    @property
    @ormcache("self.env.uid", "self.access_token")
    def _client(self):
        """
        HubSpot Client
        :rtype: HubSpot
        """
        self.ensure_one()
        return HubSpot(access_token=self.access_token)

    @api.model
    def _sale_order_field_map(self) -> Dict[str, str]:
        get_param = self.env["ir.config_parameter"].sudo().get_param
        xmlid = "hubspot_quotation_connector.sale_order_field_map"
        return safe_eval(get_param(xmlid, default="{}"))

    @api.model
    def _hubspot_field_convert(self, props: Dict[str, Any]) -> Dict[str, Any]:
        field_map = self._sale_order_field_map()
        return {
            field_map[key]: value for key, value in props.items() if key in field_map
        }

    @api.model
    def remote_field(self, name: str) -> str:
        return self._sale_order_field_map()[name]

    def get_deals_by_partner(
        self,
        partner_id: "odoo.model.res_partner",
        properties: List[str] = None,
        limit: int = None,
    ) -> List[SimplePublicObject]:
        contact_items = self.get_contact_by_email(partner_id.email)
        if not contact_items:
            return []
        deal_filters = [
            DealsFilter(
                property_name="associations.contact",
                operator="IN",
                values=[item.id for item in contact_items],
            )
        ]
        order_number_field = self._sale_order_field_map().get("order_number")
        if order_number_field:
            deal_filters.append(
                DealsFilter(
                    property_name=order_number_field,
                    operator="NOT_HAS_PROPERTY",
                )
            )
        response = self._client.crm.deals.search_api.do_search(
            public_object_search_request=DealsSearchRequest(
                filter_groups=[DealsFilterGroup(deal_filters)],
                limit=limit,
                properties=properties,
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
                                property_name="email", operator="EQ", value=email
                            )
                        ]
                    )
                ],
                limit=limit,
            )
        )
        return response.results

    def update_deal(self, deal_object_id: int, values: Dict):
        return self._client.crm.deals.basic_api.update(
            deal_id=deal_object_id,
            simple_public_object_input=DealInput(
                properties=self._hubspot_field_convert(values)
            ),
        )

    def read_deal(self, deal_object_id: int, properties: List[str] = None):
        return self._client.crm.deals.basic_api.get_by_id(
            deal_id=deal_object_id, properties=properties
        )

    @staticmethod
    def datetime_parse(value: Union[date, datetime]) -> int:
        if isinstance(value, date):
            value = datetime.combine(value, datetime.min.time())
        return int(value.timestamp() * 1000)

    @staticmethod
    def notification(message: str, message_type: str = "success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("HubSpot"),
                "message": message,
                "type": message_type,
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
