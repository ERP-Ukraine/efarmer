from odoo import api, fields, models, tools


class EfarmerSaleReport(models.Model):
    _name = 'efarmer.sale.report'
    _description = 'eFarmer Sale Report'
    _order = 'id DESC'
    _auto = False

    product_code = fields.Char('Product Code', readonly=True)
    product_id = fields.Many2one('product.product', 'Product Name', readonly=True)
    quantity = fields.Float('Quantity', readonly=True, group_operator='sum')
    revenue = fields.Float('Revenue', readonly=True, group_operator='sum')
    margin = fields.Float('Margin', readonly=True, group_operator='sum')
    country_id = fields.Many2one('res.country', 'Country', readonly=True)
    sales_person_id = fields.Many2one('res.users', 'Sale Person', readonly=True)
    sale_order_no = fields.Char('Quotation Number', readonly=True)

    invoice_no = fields.Char('Invoice #', readonly=True)
    invoice_create_date = fields.Datetime('Invoice create date', readonly=True)
    invoice_paid_date = fields.Datetime('Invoice paid date', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW %s AS (
                %s %s %s %s
            )
        ''' % (
            self._table, self._select(), self._from(), self._where(), self._group_by()
        ))

    @api.model
    def _select(self):
        return '''
            SELECT
                sol.id AS id,
                sol.salesman_id AS sales_person_id,
                sol.margin AS margin,
                sol.product_uom_qty AS quantity,
                sol.price_total AS revenue,

                product.default_code AS product_code,
                product.id AS product_id,

                customer.country_id AS country_id,
                so.name AS sale_order_no,

                string_agg(DISTINCT am.name, ', ') AS invoice_no,
                MIN(aml.create_date) AS invoice_create_date,
                MAX(payment.create_date) AS invoice_paid_date
        '''

    @api.model
    def _from(self):
        return '''
            FROM sale_order_line AS sol
                LEFT JOIN sale_order AS so ON so.id = sol.order_id
                LEFT JOIN product_product AS product ON product.id = sol.product_id
                LEFT JOIN res_partner AS customer ON customer.id = sol.order_partner_id

                LEFT JOIN sale_order_line_invoice_rel AS sol_aml_rel ON sol_aml_rel.order_line_id = sol.id
                LEFT JOIN account_move_line AS aml ON aml.id = sol_aml_rel.invoice_line_id
                LEFT JOIN account_move AS am ON am.id = aml.move_id

                -- The nested select is used to bind moves (invoices) with their payments.
                LEFT JOIN (

                    SELECT
                        am.id AS move_id,
                        payment_aml.payment_id AS payment_id
                    FROM account_move_line AS payment_aml
                    JOIN account_partial_reconcile AS apc ON apc.credit_move_id = payment_aml.id
                    JOIN account_move_line AS invoice_aml ON invoice_aml.id = apc.debit_move_id
                    JOIN account_move AS am ON am.id = invoice_aml.move_id
                    WHERE payment_aml.payment_id IS NOT NULL
                    GROUP BY
                        am.id,
                        payment_aml.payment_id

                    UNION

                    SELECT
                        am.id AS move_id,
                        payment_aml.payment_id AS payment_id
                    FROM account_move_line AS payment_aml
                    JOIN account_partial_reconcile AS apc ON apc.debit_move_id = payment_aml.id
                    JOIN account_move_line AS invoice_aml ON invoice_aml.id = apc.credit_move_id
                    JOIN account_move AS am ON am.id = invoice_aml.move_id
                    WHERE payment_aml.payment_id IS NOT NULL
                    GROUP BY
                        am.id,
                        payment_aml.payment_id

                ) AS move_payment_rel ON move_payment_rel.move_id = am.id
                LEFT JOIN account_payment AS payment ON payment.id = move_payment_rel.payment_id
        '''

    @api.model
    def _where(self):
        return '''
            WHERE
                product.id != CAST((COALESCE((SELECT value FROM ir_config_parameter WHERE key='sale.default_deposit_product_id'), '-1')) as INT)
        '''

    @api.model
    def _group_by(self):
        return '''
            GROUP BY
                sol.id,
                sol.salesman_id,
                sol.margin,
                sol.product_uom_qty,
                sol.price_total,
                product.default_code,
                product.id,
                customer.country_id,
                so.name
        '''
