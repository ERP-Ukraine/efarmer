from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class JPKTDocumentType(models.Model):

    _name = 'jpk.document.type'
    _description = 'JPK Document Type'

    name = fields.Char(required=1, size=100)
    active = fields.Boolean(default=True)
    jpk_type = fields.Selection(
        [
            ('JPK', 'JPK - documents sent cyclically'),
            ('JPKAH', 'JPKAH - ad-hoc sending of documents during inspection'),
        ],
        default='JPK',
        required=1,
    )
    system_code = fields.Char(required=1, size=100)
    schema_version = fields.Char(required=1, size=100)
    description = fields.Text()

    # xsd do sprawdzania poprawnosci zalaczonego pliku
    xsd_id = fields.Many2one('ir.attachment')
    xsd_id_name = fields.Char(related='xsd_id.name', readonly=0, string='XSD Filename')
    xsd_id_datas = fields.Binary(related='xsd_id.datas', readonly=0, string='XSD File')

    @api.constrains('system_code', 'schema_version', 'name')
    def constrains_unique_values(self):
        for record in self:
            # using odoo constrains instead of sql constrains because sql constrains is not removed automatically
            # when removed from odoo, causing problems
            if (
                self.search(
                    [('system_code', '=', record.system_code), ('schema_version', '=', record.schema_version)],
                    count=True,
                )
                > 1
            ):
                raise ValidationError(_('System Code & Schema Version must be unique'))

            if self.search([('name', '=', record.name)], count=True) > 1:
                raise ValidationError(_('Name must be unique'))

    @api.onchange('xsd_id_datas')
    def create_attachment(self):
        if not self.xsd_id and self.xsd_id_datas:
            self.xsd_id = (
                self.env['ir.attachment']
                .create({'name': self.xsd_id_name, 'type': 'binary', 'datas': self.xsd_id_datas})
                .id
            )
