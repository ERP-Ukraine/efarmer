# See LICENSE file for full copyright and licensing details.

from odoo import models


class IntegrationImageMixin(models.AbstractModel):
    _name = 'integration.image.mixin'
    _description = 'Integration Image Mixin'

    _image_name = 'image_1920'

    @property
    def image_checksum(self):
        self.env.cr.execute(
            """
            SELECT checksum
            FROM ir_attachment
            WHERE res_model = %s AND res_id = %s AND res_field = %s
            """, (self._name, self.id, self._image_name)
        )
        select = self.env.cr.fetchone()
        return select[0] if select else False

    @property
    def has_payload(self):
        return bool(self.get_b64_data())

    @property
    def is_product(self):
        return self._name in ('product.product', 'product.template')

    @property
    def is_image(self):
        return self._name == 'product.image'

    def get_b64_data(self):
        return getattr(self, self._image_name)

    def is_image_from_parent(self):
        return False
