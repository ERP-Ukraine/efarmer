# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, models, fields
from odoo.exceptions import UserError

import io
import base64
from PIL import Image


LOGOTYPE_W = 500
LOGOTYPE_H = 500


class Company(models.Model):
    _inherit = 'res.company'

    barcode_on_picking_document = fields.Boolean(
        string='Show Sales Order Barcode on Picking document',
        help='Showing a barcode of the related sales order on all printed picking documents',
    )

    force_lot_validation_on_inventory_adjustment = fields.Boolean(
        string='Force Lot Validation on Inventory Adjustment',
    )

    logotype_file = fields.Binary('Ventor Application Logo File', default=False)

    def _validate_logotype(self, vals):
        if not vals.get('logotype_file'):
            return False

        dat = base64.decodebytes(vals.get('logotype_file'))

        image = Image.open(io.BytesIO(dat))
        if image.format.lower() != 'png':
            raise UserError(
                _(
                    'Apparently, the logotype is not a .png file'
                    ' or the file was incorrectly converted to .png format'
                )
            )

        if int(image.width) < LOGOTYPE_W or int(image.height) < LOGOTYPE_H:
            raise UserError(
                _(
                    'The logotype can\'t be less than {}x{} px.'.format(LOGOTYPE_W, LOGOTYPE_H)
                )
            )

        return True

    def write(self, vals):
        if 'logotype_file' in vals:
            self._validate_logotype(vals)
        res = super(Company, self).write(vals)
        return res
