from odoo import models
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _x_ksef_retrieve_product(self, name=None, default_code=None, barcode=None, company_id=None, extra_domain=None):
        if name and '\n' in name:
            # cut Sales Description from the name
            name = name.split('\n')[0]

        domains = []
        if barcode:
            domains.append([('barcode', '=', barcode)])

        if default_code:
            domains.append([('default_code', '=', default_code)])

        if name:
            domains += [[('name', '=', name)], [('name', 'ilike', name)]]

        company_id = company_id or self.env.company

        for company_domain in (
            [('company_id', '=', company_id.id)],
            [('company_id', '=', False)],
        ):
            for domain in domains:
                product_id = self.env['product.product'].search(
                    expression.AND(
                        [
                            domain,
                            company_domain,
                            extra_domain,
                        ]
                    ),
                    limit=1,
                )

                if product_id:
                    return product_id

        return self.env['product.product']
