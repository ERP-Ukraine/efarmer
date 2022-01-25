domain = [
    ('order_id.date_order', '>=', '2020-12-01 00:00:00'),
    ('order_id.date_order', '<=', '2021-12-31 23:59:59'),
    ('order_id.state', 'in', ['sale', 'done']),
    ('product_id', '!=', 127),
]
sols = self.env['sale.order.line'].search(domain)

res = []
for sol in sols:
    amls = sol.invoice_lines.filtered(lambda x: x.move_id.state == 'posted')
    sms = sol.move_ids.filtered(lambda x: x.state == 'done')
    svls = sms.mapped('stock_valuation_layer_ids')
    cost = sum(-svl.unit_cost if svl.quantity > 0 else svl.unit_cost for svl in svls) / (len(svls) or 1)
    if not amls or not sms or not svls or not sol.qty_invoiced:
        continue
    if any(d.year != 2021 for d in amls.mapped('move_id.invoice_date')):
        continue
    line = {
        'product': sol.product_id.name,
        'name': sol.name,
        'qty_invoiced': sol.qty_invoiced,
        'price_unit_untaxed': sol.untaxed_amount_invoiced / sol.qty_invoiced,
        'unit_cost': cost,
        'order': sol.order_id.name,
        'invoices': ', '.join(amls.mapped('move_id.name')),
        'invoices_dates': ', '.join(d.strftime('%d.%m.%Y') for d in amls.mapped('move_id.invoice_date')),
        'deliveries': ', '.join(sms.mapped('picking_id.name')),
        'delivery_dates': ', '.join(d.strftime('%d.%m.%Y') for d in sms.mapped('picking_id.date_done')),
    }
    res.append(line)

import csv
csv_columns = ['product','name','qty_invoiced', 'price_unit_untaxed', 'unit_cost', 'order', 'invoices', 'invoices_dates', 'deliveries', 'delivery_dates']
csv_file = "/tmp/sales.csv"
with open(csv_file, 'w') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
    writer.writeheader()
    for data in res:
        writer.writerow(data)
