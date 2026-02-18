# See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields

from ...tools import _compute_checksum


class IntegrationEcommerceProductImageMapping(models.Model):
    _name = 'integration.ecommerce.product.image.mapping'
    _inherits = {'integration.ecommerce.product.image.external': 'external_image_id'}
    _description = 'E-Commerce Product Image Mapping'

    external_image_id = fields.Many2one(
        string='External Image',
        comodel_name='integration.ecommerce.product.image.external',
        ondelete='cascade',
        required=True,
    )

    ttype = fields.Selection(
        string='Image Type',
        selection=[
            ('product.product', 'Variant'),
            ('product.template', 'Template'),
        ],
        default='product.template',
        required=True,
    )

    variant_code = fields.Char(
        string='Variant',
        size=33,
        # The variant_code field have to be in the mapping class due to
        # the multiple variant-mappings may reffer to the same external record
    )

    is_cover = fields.Boolean(
        string='Is Cover',
    )

    res_id = fields.Integer(
        string='Odoo ID',
        index=True,
    )

    res_name = fields.Char(
        string='Name',
        compute='_compute_res_name',
    )

    image_id = fields.Many2one(
        string='OdooImage',
        comodel_name='ecommerce.product.image',
    )

    image_db_id = fields.Integer(
        string='Image ID',
        related='image_id.id',
    )

    action_type = fields.Selection(
        string='Action Type',
        selection=[
            ('none', 'none'),
            ('pending', 'pending'),
            ('assign', 'assign'),
            ('create', 'create'),
        ],
        default='none',
        required=True,
    )

    sync_required = fields.Boolean(
        string='Sync Required',
        compute='_compute_sync_required',
    )

    checksum = fields.Char(
        string='Checksum/SHA1 (stored)',
        size=40,
    )

    checksum_compute = fields.Char(
        string='Checksum/SHA1 (computed)',
        compute='_compute_checksum_compute',
        size=40,
    )

    @api.depends('res_id', 'ttype')
    def _compute_res_name(self):
        for rec in self:
            record = rec.odoo_record
            rec.res_name = f'[{record.id}] {record.display_name}'

    @api.depends('res_id', 'is_cover', 'image_id')
    def _compute_checksum_compute(self):
        for rec in self:
            record = rec.odoo_image_record
            rec.checksum_compute = record.image_checksum if record else False

    @api.depends('checksum', 'checksum_compute')
    def _compute_sync_required(self):
        for rec in self:

            if not rec.to_none:
                value = True
            elif rec.checksum and rec.checksum_compute:
                value = rec.checksum != rec.checksum_compute
            else:
                value = True

            if not value:
                record = rec.odoo_image_record

                if rec.is_cover:
                    value = record.is_image
                else:
                    value = record.is_product

            rec.sync_required = value

    @property
    def is_template(self):
        return self.ttype == 'product.template'

    @property
    def is_variant(self):
        return self.ttype == 'product.product'

    @property
    def to_create(self):
        return self.action_type == 'create'

    @property
    def to_none(self):
        return self.action_type == 'none'

    @property
    def to_assign(self):
        return self.write({'action_type': 'assign'})

    @property
    def in_pending(self):
        return self.action_type == 'pending'

    @property
    def odoo_record(self):
        return self.env[self.ttype].browse(self.res_id)

    @property
    def odoo_image_record(self):
        record = self.odoo_record
        if not record:
            return record
        return self.image_id or record

    @property
    def product_template_id(self):
        if self.is_template:
            return self.res_id
        return self.odoo_record.product_tmpl_id.id

    @property
    def product_variant_id(self):
        if self.is_template:
            return False
        return self.res_id

    def mark_none(self):
        return self.write({'action_type': 'none'})

    def mark_assign(self):
        return self.write({'action_type': 'assign'})

    def mark_create(self):
        return self.write({'action_type': 'create'})

    def mark_pending(self):
        return self.write({'action_type': 'pending'})

    def get_external_sku(self):
        external = self.odoo_record.to_external_record(self.integration_id)
        return external.external_reference

    def set_checksum(self, b64_bytes):
        value = _compute_checksum(b64_bytes)
        self.checksum = value
        return value

    def get_b64_data(self):
        record = self.odoo_image_record
        return record.get_b64_data()

    def apply_binary_data(self, b64_bytes):
        self.image_id.unlink()
        record = self.odoo_record

        if self.is_cover:
            record.image_1920 = b64_bytes
        else:
            image = self.env['ecommerce.product.image'].create({
                'name': self.external_image_id.name.rsplit('.', 1)[0],
                'product_tmpl_id': self.product_template_id,
                'product_variant_id': self.product_variant_id,
                'image_1920': b64_bytes,
            })
            self.image_id = image.id

        return True

    def action_open_product(self):
        record = self.odoo_record
        return record.get_formview_action()
