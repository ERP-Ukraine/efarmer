from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pl_trilab')
    def _get_pl_trilab_template_data(self):
        return {
            'property_account_receivable_id': 'chart20001',
            'property_account_payable_id': 'chart20501',
            'property_account_expense_categ_id': 'chart73101',
            'property_account_income_categ_id': 'chart73001',
            'property_stock_account_input_categ_id': 'chart30001',
            'property_stock_account_output_categ_id': 'chart30501',
            'property_stock_valuation_account_id': 'chart33001',
            'code_digits': '3',
            'use_storno_accounting': True,
            'name': 'COA by Trilab',
        }

    @template('pl_trilab', 'res.company')
    def _get_pl_trilab_res_company(self):
        return {
            self.env.company.id: {
                'anglo_saxon_accounting': True,
                'display_invoice_amount_total_words': True,
                'account_fiscal_country_id': 'base.pl',
                'bank_account_code_prefix': '130.01.01',
                'cash_account_code_prefix': '101.01.01',
                'transfer_account_code_prefix': '149.01',
                'account_default_pos_receivable_account_id': 'chart21001',
                'income_currency_exchange_account_id': 'chart75031',
                'expense_currency_exchange_account_id': 'chart75131',
                'account_journal_early_pay_discount_gain_account_id': 'chart76004',
                'account_journal_early_pay_discount_loss_account_id': 'chart76104',
                'default_cash_difference_income_account_id': 'chart76004',
                'default_cash_difference_expense_account_id': 'chart76104',
                'account_journal_suspense_account_id': 'chart13099',
                'deferred_expense_account_id': 'chart64001',
                'deferred_revenue_account_id': 'chart84901',
            }
        }
