from itertools import count
from odoo import api, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    @api.model
    def get_creation_vals_for_tilda_webhook(self, kwargs, creation_vals):
        assert isinstance(kwargs, dict)
        assert isinstance(creation_vals, dict)

        orderid = kwargs.get('payment[orderid]')
        if orderid:
            won_stage = self.env['crm.stage'].search([('is_won', '=', True)], limit=1)

            product_notes = []
            for index in count(0):
                name = kwargs.get('payment[products][' + str(index) + '][name]')
                if not name:
                    break

                product_notes.append('\n'.join((
                    'Product: ' + name,
                    'Quantity: ' + kwargs.get('payment[products][' + str(index) + '][quantity]', ''),
                    'Price: ' + kwargs.get('payment[products][' + str(index) + '][price]', ''),
                    'Amount: ' + kwargs.get('payment[products][' + str(index) + '][amount]', ''),
                )))

            description = creation_vals.get('description', '') + '\n\n' + '\n\n'.join(product_notes + [
                'Total Amount: ' + kwargs.get('payment[amount]', ''),
                'Order ID: ' + orderid,
            ])

            creation_vals.update({
                'type': 'opportunity',
                'stage_id': won_stage.id,
                'description': description,
            })
        else:
            creation_vals['type'] = 'lead'

        return creation_vals
