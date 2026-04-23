from odoo import fields, models


class KsefSettings(models.Model):
    _name = 'ksef.settings'
    _description = 'KSeF Settings'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)

    endpoint_url = fields.Char(string='API Endpoint URL', required=True)
    qr_code_url = fields.Char(string='QR Code URL', required=True)

    public_asymmetric_key_id = fields.Many2one('ir.attachment', required=True)
    public_asymmetric_key_id_datas = fields.Binary(
        related='public_asymmetric_key_id.datas', readonly=False, string='Public Asymmetric Key Datas'
    )
    public_asymmetric_key_id_name = fields.Char(
        related='public_asymmetric_key_id.name', readonly=False, string='Public Asymmetric Key Filename'
    )

    public_symmetric_key_id = fields.Many2one('ir.attachment', required=True)
    public_symmetric_key_id_datas = fields.Binary(
        related='public_symmetric_key_id.datas', readonly=False, string='Public Symmetric Key Datas'
    )
    public_symmetric_key_id_name = fields.Char(
        related='public_symmetric_key_id.name', readonly=False, string='Public Symmetric Key Filename'
    )
