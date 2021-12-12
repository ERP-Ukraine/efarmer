import io
import base64
from collections import defaultdict
from odoo import api, fields, models
from odoo.tools import PatchedXlsxWorkbook


class EfarmerShipingReport(models.TransientModel):
    _name = 'efarmer.shipping.report'
    _description = 'eFarmer Shipping Report'

    date_from = fields.Datetime()
    date_to = fields.Datetime()

    _sql_constraints = [
        ('valid_dates', 'CHECK(date_from <= date_to)', 'Date from must be greater than or equal to that date to.'),
    ]

    def build(self):
        self.ensure_one()

        pickings = self._get_filtered_pickings()
        report_data = self._build_report_data(pickings)
        report_bytes = self._get_report_bytes(report_data)
        report_encoded_bytes = base64.b64encode(report_bytes.read())

        report_name = 'Shipping Report'
        if self.date_from:
            report_name += ' from {0:%d.%m.%Y}'.format(self.date_from)
        if self.date_to:
            report_name += ' to {0:%d.%m.%Y}'.format(self.date_to)
        report_name += '.xlsx'

        report_mark = 'Shipping Report'
        attach = self.env['ir.attachment'].search([('description', '=', report_mark)], limit=1)
        if attach:
            attach.write({
                'name': report_name,
                'datas': report_encoded_bytes,
            })
        else:
            attach = self.env['ir.attachment'].create({
                'name': report_name,
                'type': 'binary',
                'description': report_mark,
                'datas': report_encoded_bytes,
            })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/{}/{}'.format(attach.id, report_name),
            'target': 'self',
        }

    def _get_filtered_pickings(self):
        self.ensure_one()
        domain = [('state', 'in', ['assigned', 'done']), ('picking_type_code', '=', 'outgoing')]

        if self.date_from:
            domain.extend(['|', ('date_done', '=', False), ('date_done', '>=', self.date_from)])
        if self.date_to:
            domain.extend(['|', ('date_done', '=', False), ('date_done', '<=', self.date_to)])

        return self.env['stock.picking'].search(domain)

    @api.model
    def _build_report_data(self, pickings):
        """Returns
        {
            products: <<product.product recordset>>,
            moves: {
                (order, picking, partner): {
                    product_id: <<stock.move recordset>>
                }
            }
        }
        """
        report_data = {
            'products': self.env['product.product'],
            'moves': {},
        }

        for move in pickings.mapped('move_lines').filtered(lambda x: x.state != 'cancel'):
            order = move.sale_line_id.order_id
            picking = move.picking_id
            partner = picking.partner_id or order.partner_id
            product = move.product_id

            report_data['products'] |= product

            data_key = (order, picking, partner)
            data_by_key = report_data['moves'].get(data_key)
            if not data_by_key:
                data_by_key = defaultdict(self.get_empty_stock_move_recordset)
                report_data['moves'][data_key] = data_by_key
            data_by_key[product.id] |= move

        return report_data

    @api.model
    def _get_report_bytes(self, report_data):
        stream = io.BytesIO()

        with PatchedXlsxWorkbook(stream) as workbook:
            worksheet = workbook.add_worksheet()
            row_no = 0

            header_format = workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
            })

            cell_format = workbook.add_format({
                'align': 'center',
                'valign': 'bottom',
            })

            product_cell_format = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
            })

            worksheet.set_column(0, 0, 20)
            worksheet.set_column(1, 1, 10)
            worksheet.set_column(2, 2, 15)
            worksheet.set_column(3, 3, 25)
            worksheet.set_column(4, 4, 25)
            worksheet.set_column(5, 5, 15)
            worksheet.set_column(6, 6, 30)

            # First row

            worksheet.write(row_no, 0, 'Date of shipping', header_format)
            worksheet.write(row_no, 1, 'SO #', header_format)
            worksheet.write(row_no, 2, 'Delivery #', header_format)
            worksheet.write(row_no, 3, 'Name of Customer', header_format)
            worksheet.write(row_no, 4, 'Address', header_format)
            worksheet.write(row_no, 5, 'Country', header_format)
            worksheet.write(row_no, 6, 'Email', header_format)
            col_no = 7

            for product in report_data['products']:
                worksheet.set_column(col_no, col_no, 15)
                worksheet.write(row_no, col_no, product.name, header_format)
                col_no += 1

            # Other rows

            for data_key, move_info in report_data['moves'].items():
                order, picking, partner = data_key
                row_no += 1

                worksheet.write(row_no, 0, picking.date_done.strftime('%d/%m/%Y') if picking.date_done else '', cell_format)
                worksheet.write(row_no, 1, order.name or '', cell_format)
                worksheet.write(row_no, 2, picking.name or '', cell_format)
                worksheet.write(row_no, 3, partner.name or '', cell_format)
                worksheet.write(row_no, 4, self._get_partner_address(partner))
                worksheet.write(row_no, 5, partner.country_id.name or '', cell_format)
                worksheet.write(row_no, 6, partner.email or '', cell_format)
                col_no = 7

                for product in report_data['products']:
                    moves = move_info.get(product.id)
                    if moves:
                        lot_names = moves.mapped('move_line_ids.lot_id.name')

                        # Display either lots (if exists)
                        if lot_names:
                            worksheet.write(row_no, col_no, ',\n'.join(lot_names), product_cell_format)
                        # Or quantity
                        else:
                            qty = sum(moves.mapped(lambda x: x.quantity_done if x.state == 'done' else x.reserved_availability))
                            worksheet.write(row_no, col_no, str(qty), product_cell_format)

                    col_no += 1

            worksheet.freeze_panes(1, 0)

        stream.seek(0)
        return stream

    @api.model
    def _get_partner_address(self, partner):
        parts = []

        for field_ in ('street', 'street2', 'city', 'state_id', 'zip', 'country_id'):
            value = getattr(partner, field_)
            if value:
                parts.append(value.name if field_ == 'state_id' or field_ == 'country_id' else value)

        return ',\n'.join(parts)

    @api.model
    def get_empty_stock_move_recordset(self):
        return self.env['stock.move']
