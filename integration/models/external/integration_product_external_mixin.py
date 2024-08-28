# See LICENSE file for full copyright and licensing details.

from odoo import models


class IntegrationProductExternalMixin(models.AbstractModel):
    _name = 'integration.product.external.mixin'
    _description = 'Integration Product External Mixin'

    def _create_internal_import_line(self):
        return self.env['import.product.line'].create({
            'origin_id': self.id,
            'name': self.name,
            'code': self.code,
            'reference': self.external_reference,
            'barcode': self.external_barcode,
            'mapping_id': self.mapping_record.id,
            'odoo_id': self.odoo_record.id,
            'model_name': self._odoo_model,
            'type': 'internal',
        })
