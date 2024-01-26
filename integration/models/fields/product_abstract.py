# See LICENSE file for full copyright and licensing details.


class ProductAbstractSend:
    """
    Common logic for `product template` and `product variant`
    Odoo classes during sending to external.
    """

    def _collect_specific_prices(self, pricelist_ids=None, item_ids=None, raise_error=False):
        result = list()
        integration = self.integration

        if item_ids:
            x_item_ids = self.odoo_obj._search_pricelist_items(i_ids=item_ids)
        else:
            x_pricelist_ids = pricelist_ids or integration._search_pricelist_mappings()
            x_item_ids = self.odoo_obj._search_pricelist_items(p_ids=x_pricelist_ids)

        if not x_item_ids:
            return result

        for rec in x_item_ids:
            vals = rec.to_export_format(integration, self.odoo_obj._name, raise_error=raise_error)
            result.append(vals)

        return result


class ProductAbstractReceive:
    """
    Common logic for `product template` and `product variant`
    Odoo classes during receiving from external.
    """
    pass
