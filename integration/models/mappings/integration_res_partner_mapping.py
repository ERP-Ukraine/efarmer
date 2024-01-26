# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationResPartnerMapping(models.Model):
    _name = 'integration.res.partner.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Res Partner Mapping'
    _mapping_fields = ('partner_id', 'external_partner_id')

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        ondelete='cascade',
    )

    external_partner_id = fields.Many2one(
        comodel_name='integration.res.partner.external',
        required=True,
        ondelete='cascade',
    )
