# See LICENSE file for full copyright and licensing details.

import logging
from io import BytesIO

from PIL import Image

try:
    from PIL import UnidentifiedImageError
except ImportError:
    UnidentifiedImageError = IOError

from odoo import models, _
from odoo.tools.image import IMAGE_MAX_RESOLUTION


_logger = logging.getLogger(__name__)


class IntegrationProductExternalMixin(models.AbstractModel):
    _name = 'integration.product.external.mixin'
    _description = 'Integration Product External Mixin'

    @staticmethod
    def verify_image_data(template, bin_data):
        mess_pref = _('%s image error: ') % str(template)

        try:
            img = Image.open(BytesIO(bin_data))
        except UnidentifiedImageError as e:
            _logger.error(mess_pref + str(e))
            return False

        w, h = img.size
        resolution_ok = w * h <= IMAGE_MAX_RESOLUTION

        if not resolution_ok:
            _logger.error(mess_pref + _('Image resolution is higher than Odoo allows'))
            return False

        return resolution_ok

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
