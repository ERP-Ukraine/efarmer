from odoo import api, fields, models


class JpkDocumentMixin(models.AbstractModel):
    _name = 'jpk.document.mixin'
    _description = 'JPK Document Mixin'

    year = fields.Integer(string='Year', required=True)
    month = fields.Integer(string='Month', required=True)

    cel_zlozenia = fields.Integer(string='Cel złożenia')
    version = fields.Char(string='JPK Version', required=True)

    document_type_id = fields.Many2one('jpk.document.type', required=True)

    source_xml = fields.Binary()

    is_jpk_transfer_installed = fields.Boolean(compute='_compute_jpk_transfer')

    @api.depends_context('company')
    def _compute_jpk_transfer(self):
        for document_id in self:
            document_id.is_jpk_transfer_installed = self.env.company.x_is_jpk_transfer_installed()

    def get_transfer_info(self):
        self.ensure_one()

        if self.is_jpk_transfer_installed and (
            transfer_id := self.env['jpk.transfer'].search(
                [('reference_document', '=', f'{self._name},{self.id}'), ('confirmation_id', '!=', False)], limit=1
            )
        ):
            return {'reference_number': transfer_id.reference_number}

        return {}

    def action_generate_xml(self):
        raise NotImplementedError
