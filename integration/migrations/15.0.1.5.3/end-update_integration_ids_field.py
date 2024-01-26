from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    Update `Sales Integrations` field for Product Variants
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    env.cr.execute(
        """
        INSERT INTO sale_integration_product_variant
        SELECT pp.id, sip.sale_integration_id
        FROM product_product AS pp JOIN sale_integration_product AS sip
        ON pp.product_tmpl_id = sip.product_id
        """
    )
