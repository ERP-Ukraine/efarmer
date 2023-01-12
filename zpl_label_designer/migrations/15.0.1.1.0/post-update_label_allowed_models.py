from odoo import api, SUPERUSER_ID


ALLOWED_MODELS_TO_ZLD_LABEL = (
    'product.product', 'product.template',
    'stock.production.lot', 'stock.quant.package'
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    companies = env['res.company'].search([])
    allowed_model_ids = env['ir.model'].search([
        ('model', 'in', ALLOWED_MODELS_TO_ZLD_LABEL)]).mapped('id')

    for company in companies:
        company.zld_allowed_models = [(6, 0, allowed_model_ids)]
