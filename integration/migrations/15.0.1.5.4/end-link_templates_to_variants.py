from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    Link external product templates and external product variants to each other
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    ExternalTemplate = env['integration.product.template.external']
    ExternalVariant = env['integration.product.product.external']

    external_templates = ExternalTemplate.search([])
    for template in external_templates:
        external_variants = ExternalVariant.search([
            ('code', '=like', template.code + '-%'),
            ('integration_id', '=', template.integration_id.id),
        ])
        external_variants.external_product_template_id = template.id
