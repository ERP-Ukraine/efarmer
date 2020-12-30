# odoo shell
def fix_valuation(product_id=False, qty=0, value=0, counterpart_account_id=363):
    company_id = self.env.company
    product = self.env['product.product'].browse(product_id)
    if product.cost_method not in ('standard', 'average'):
        return
    unit_price = value / qty if qty != 0 else 0
    svl_vals = {
        'company_id': company_id.id,
        'product_id': product.id,
        'description': ('Product value manually modified'),
        'value': value,
        'quantity': qty,
        'unit_cost': unit_price,
    }
    stock_valuation_layers = self.env['stock.valuation.layer'].sudo().create(svl_vals)
    # Handle account moves.
    product_accounts = {product.id: product.product_tmpl_id.get_product_accounts()}
    am_vals_list = []
    for stock_valuation_layer in stock_valuation_layers:
        product = stock_valuation_layer.product_id
        value = stock_valuation_layer.value
        if product.valuation != 'real_time':
            continue
        if value < 0:
            debit_account_id = counterpart_account_id
            credit_account_id = product_accounts[product.id]['stock_valuation'].id
        else:
            debit_account_id = product_accounts[product.id]['stock_valuation'].id
            credit_account_id = counterpart_account_id
        move_vals = {
            'journal_id': product_accounts[product.id]['stock_journal'].id,
            'company_id': company_id.id,
            'ref': product.default_code,
            'stock_valuation_layer_ids': [(6, None, [stock_valuation_layer.id])],
            'line_ids': [(0, 0, {
                'name': ('%s changed cost from %s to %s - %s') % (self.env.user.name, product.standard_price, unit_price, product.display_name),
                'account_id': debit_account_id,
                'debit': abs(value),
                'credit': 0,
                'product_id': product.id,
            }), (0, 0, {
                'name': ('%s changed cost from %s to %s - %s') % (self.env.user.name, product.standard_price, unit_price, product.display_name),
                'account_id': credit_account_id,
                'debit': 0,
                'credit': abs(value),
                'product_id': product.id,
            })],
        }
        am_vals_list.append(move_vals)
    account_moves = self.env['account.move'].create(am_vals_list)
    account_moves.post()

items = [
    # product, qty, value
    [213, 0, 0.03],
    [68, 0, -0.21],
    [86, 0, 0.02],
    [200, 0, -0.01],
    [178, 0, 0.01],
    [122, -1, -1985.73],
    [85, 0, 0.09],
    [60, 0, -0.07],
    [61, 0, 0.01],
    [180, 0, 0.08],
    [182, 0, 0.02],
    [149, -1, -83.13],
    [81, 0, -0.31],
    [80, 0, 0.05],
    [181, 0, 0.09],
    [197, 0, 0.01],
    [198, 0, -0.02],
    [143, -1, -99.17],
    [131, -1, -67.81],
    [63, 0, 0.01],
    [144, -2, -164.94],
    [174, 0, -25.5],
    [169, 0, -24.5],
    [74, 1, 0.0],
    [165, -4, -1470.44],
    [166, 0, 0.07],
    [123, 4, 1299.64],
    [164, 1, 166.73],
    [193, -1, -550.34],
    [104, 0, 489.61],
]

for item in items:
    fix_valuation(product_id=item[0], qty=item[1], value=item[2])
