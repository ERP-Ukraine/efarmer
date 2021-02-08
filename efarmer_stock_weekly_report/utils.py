import io
import base64
import logging
import datetime
from itertools import groupby
from collections import defaultdict

from odoo import api, fields
from odoo.exceptions import UserError
from odoo.tools import PatchedXlsxWorkbook, float_is_zero

class OrderpointInfo:

    def __init__(self, orderpoint_id, code, product_name, min_qty, max_qty, lead_time, avail_qty, forecasted_qty):
        self.orderpoint_id = orderpoint_id
        self.code = code
        self.product_name = product_name
        self.min_qty = min_qty
        self.max_qty = max_qty
        self.lead_time = lead_time
        self.avail_qty = avail_qty
        self.forecasted_qty = forecasted_qty

    def get_public_items(self):
        return (
            ('code', self.code),
            ('product_name', self.product_name),
            ('min_qty', self.min_qty),
            ('max_qty', self.max_qty),
            ('lead_time', self.lead_time),
            ('avail_qty', self.avail_qty),
            ('forecasted_qty', self.forecasted_qty),
        )

class PurchaseInfo:

    def __init__(self, code, title, date, week_no, state):
        self.code = code
        self.title = title
        self.date = date
        self.week_no = week_no
        self.state = state

    @classmethod
    def create(cls, code, po, date):
        title_tmpl = '{code} {po.name} {date:%d.%m.%Y} {po.partner_id.display_name}'

        week_no = int(date.strftime('%W'))
        first_week_of_year = int(datetime.date(date.year, 1, 1).strftime('%W'))
        if not first_week_of_year:  # when Monday is the first day of the year, the first week value is 1
            week_no += 1  # increment it beacase the %W value is zero-based

        return cls(code, title_tmpl.format(code=code, po=po, date=date), date, week_no, po.state)

    def at_finish(self):
        return self.state in ('purchase', 'done')

    def at_start(self):
        return self.state in ('draft', 'sent', 'to approve')

class TableCell:

    def __init__(self, row_no, col_no, rowspan, colspan, value, format):
        self.row_no = row_no
        self.col_no = col_no
        self.rowspan = rowspan
        self.colspan = colspan
        self.value = value
        self.format = format

class Table:

    def __init__(self):
        self._orderpoints = []
        self._red_orderpoint_ids = set()

        self._purchases = []
        self._quantities = defaultdict(float)
        self._cell_formats = {}

    def append_orderpoint_info(self, record):
        self._orderpoints.append(record)

    def append_purchase_info(self, data):
        if isinstance(data, list):
            self._purchases.extend(data)
        else:
            self._purchases.append(data)

    def add_qty(self, orderpoint_id, purchase_info, qty):
        if purchase_info.at_start():
            self._red_orderpoint_ids.add(orderpoint_id)
        self._quantities[(orderpoint_id, purchase_info)] += qty

    def set_cell_formats(self, workbook):
        regular_font = {'font_name': 'Arial', 'font_size': 10}
        header_font = {'font_name': 'Arial', 'font_size': 12}

        border = {'border': True}

        left_vcenter = {'align': 'left', 'valign': 'vcenter'}
        center_vcenter = {'align': 'center', 'valign': 'vcenter'}
        center_bottom = {'align': 'center', 'valign': 'bottom'}

        header = dict(header_font, **center_vcenter, **border, text_wrap=True)

        red = {'bg_color': '#e34138'}
        rfq = {'bg_color': '#fbd965'}
        po = {'bg_color': '#94c57e'}

        self._cell_formats['default_left'] = workbook.add_format(dict(regular_font, **left_vcenter, **border))
        self._cell_formats['default_center'] = workbook.add_format(dict(regular_font, **center_vcenter, **border))
        self._cell_formats['lead_time'] = workbook.add_format(dict(regular_font, **center_vcenter, **border, bg_color='#efefef'))

        self._cell_formats['red_default_left'] = workbook.add_format(dict(regular_font, **left_vcenter, **border, **red))
        self._cell_formats['red_default_center'] = workbook.add_format(dict(regular_font, **center_vcenter, **border, **red))

        self._cell_formats['header'] = workbook.add_format(dict(header, bold=True))
        self._cell_formats['header_green'] = workbook.add_format(dict(header, **center_bottom, bold=True, bg_color='#b7d8a9'))

        self._cell_formats['header_rotated_rfq'] = workbook.add_format(dict(header, **rfq, rotation=90))
        self._cell_formats['header_rotated_po'] = workbook.add_format(dict(header, **po, rotation=90))

        self._cell_formats['rfq'] = workbook.add_format(dict(regular_font, **center_vcenter, **border, **rfq))
        self._cell_formats['po'] = workbook.add_format(dict(regular_font, **center_vcenter, **border, **po))

    def get_frezee_col_count(self):
        return len(self._get_orderpoints_titles())

    def __iter__(self):
        # orderpoints titles
        orderpoints_titles = self._get_orderpoints_titles()
        for col_no, title in enumerate(orderpoints_titles):
            yield TableCell(0, col_no, 2, 1, title, self._cell_formats['header_green'])

        # rfq / po titles
        ordered_purchase_info = []
        col_no = len(orderpoints_titles)
        for week_no, purchases in groupby(sorted(self._purchases, key=lambda x: x.date), key=lambda x: x.week_no):
            purchases = list(purchases)
            col_width = len(purchases)

            yield TableCell(0, col_no, 1, col_width, 'week {:02d}'.format(week_no), self._cell_formats['header'])
            ordered_purchase_info.extend(purchases)
            col_no += col_width

        for col_no, purchase_info in enumerate(ordered_purchase_info, start=len(orderpoints_titles)):
            cell_format = self._cell_formats['header_rotated_rfq'] if purchase_info.code == 'RFQ' else self._cell_formats['header_rotated_po']
            yield TableCell(1, col_no, 1, 1, purchase_info.title, cell_format)

        # other rows
        row_no = 2
        for orderpoint_info in self._orderpoints:
            # This field is an array and there should be the one value per row,
            # but at least one row must exist.
            rowspan = len(orderpoint_info.lead_time) or 1

            for col_no, (field, value) in enumerate(orderpoint_info.get_public_items()):
                cell_format = self._get_orderpoint_cell_format(orderpoint_info, field)
                if field == 'lead_time':
                    for i in range(rowspan):
                        # If there is no vendors, no TableCell record is yield.
                        # But it causes a problem with red rows.
                        value_ = '' if len(orderpoint_info.lead_time) <= i else value[i]
                        yield TableCell(row_no+i, col_no, 1, 1, value_, cell_format)
                else:
                    yield TableCell(row_no, col_no, rowspan, 1, value, cell_format)

            for col_no, purchase_info in enumerate(ordered_purchase_info, start=len(orderpoints_titles)):
                cell_format = self._get_qty_cell_format(orderpoint_info, purchase_info)
                qty = self._quantities.get((orderpoint_info.orderpoint_id, purchase_info), '')
                yield TableCell(row_no, col_no, rowspan, 1, qty, cell_format)

            row_no += rowspan

    def _get_orderpoints_titles(self):
        today = fields.Date.today()
        return (
            'Internal Reference',
            'Product',
            'Minimum Quantity',
            'Maximum Quantity',
            'Lead Time',
            'CURRENT AMS/STOCK on {}'.format(today.strftime('%d/%m')),
            'Forecasted Stock',
        )

    def _is_red_row(self, orderpoint_info):
        return any((
            orderpoint_info.forecasted_qty < 0,
            orderpoint_info.orderpoint_id in self._red_orderpoint_ids,
        ))

    def _get_orderpoint_cell_format(self, orderpoint_info, field):
        if self._is_red_row(orderpoint_info):
            cell_format_name = 'red_default_left' if field in ('code', 'product_name') else 'red_default_center'
            return self._cell_formats[cell_format_name]

        if field == 'lead_time':
            return self._cell_formats['lead_time']
        elif field in ('code', 'product_name'):
            return self._cell_formats['default_left']
        else:
            return self._cell_formats['default_center']

    def _get_qty_cell_format(self, orderpoint_info, purchase_info):
        if self._is_red_row(orderpoint_info):
            return self._cell_formats['red_default_center']
        elif purchase_info.code == 'RFQ':
            return self._cell_formats['rfq']
        else:
            return self._cell_formats['po']

class StockWeeklyReportProvider:
    """
    Public API:
    - get_report() -> bytes (base64 encoded)

    Raises:
    - UserError
    """

    def __init__(self, env):
        assert isinstance(env, api.Environment)
        self._env = env

        self._logger = logging.getLogger(__name__)

    def get_report(self):
        location = self._get_location()
        io_bytes = self._gen_report(location)
        self._logger.info('A Stock Weekly Report was generated successfully!')
        return base64.b64encode(io_bytes.read())

    def _get_location(self):
        domain = [('used_for_efarmer_stock_weekly_report', '=', True)]
        location = self._env['stock.location'].sudo().search(domain)

        if len(location) < 1:
            raise UserError('You should select a location to use in Stock Weekly Report.')

        if len(location) > 1:
            error = ('You should select only one location to use in Stock Weekly Report. '
                     'Now you have {} ones: {}.')
            raise UserError(error.format(len(location), location.mapped('name')))

        return location

    def _gen_report(self, location):
        Orderpoint = self._env['stock.warehouse.orderpoint']
        orderpoints = Orderpoint.sudo().search([]).with_context({'location': location.id})

        table = Table()
        self._put_orderpoints_to_table(orderpoints, table)
        self._put_purchases_to_table(orderpoints, table)

        stream = io.BytesIO()
        with PatchedXlsxWorkbook(stream) as workbook:
            table.set_cell_formats(workbook)
            worksheet = workbook.add_worksheet()

            worksheet.set_row(1, 150)
            worksheet.set_column(0, 0, 25)
            worksheet.set_column(1, 1, 35)
            worksheet.set_column(2, 2, 12)
            worksheet.set_column(3, 3, 12)
            worksheet.set_column(4, 4, 25)
            worksheet.set_column(5, 5, 15)
            worksheet.set_column(6, 6, 15)

            for cell in table:
                if cell.rowspan > 1 or cell.colspan > 1:
                    x1, y1  = cell.row_no, cell.col_no
                    x2, y2 = cell.row_no + cell.rowspan - 1, cell.col_no + cell.colspan - 1
                    worksheet.merge_range(x1, y1, x2, y2, cell.value, cell.format)
                else:
                    worksheet.write(cell.row_no, cell.col_no, cell.value, cell.format)

            worksheet.freeze_panes(2, table.get_frezee_col_count())

        stream.seek(0)
        return stream

    def _put_orderpoints_to_table(self, orderpoints, table):
        def map_sellers_to_lead_time(sellers):
            if len(sellers) > 1:
                return sellers.mapped(lambda x: '{} days - {}'.format(x.delay, x.name.display_name or ''))
            elif sellers:
                return [str(sellers.delay) + ' days']
            else:
                return []

        for orderpoint in orderpoints:
            table.append_orderpoint_info(OrderpointInfo(
                orderpoint.id,
                orderpoint.product_id.default_code or '',
                orderpoint.product_id.name,
                orderpoint.product_min_qty,
                orderpoint.product_max_qty,
                map_sellers_to_lead_time(orderpoint.product_id.seller_ids),
                orderpoint.product_id.qty_available,
                orderpoint.product_id.virtual_available,
            ))

    def _put_purchases_to_table(self, orderpoints, table):
        orderpoint_products = orderpoints.mapped('product_id')

        for po in self._env['purchase.order'].sudo().search([('state', '!=', 'cancel')]):
            valid_po_lines = po.order_line.filtered(lambda x: x.product_id in orderpoint_products)

            if po.is_shipped or not valid_po_lines:
                continue

            # create a record from the RFQ
            purchase_info = PurchaseInfo.create('RFQ', po, po.date_order)
            table.append_purchase_info(purchase_info)

            for pol in valid_po_lines:
                orderpoint = orderpoints.filtered(lambda x: x.product_id == pol.product_id)[:1].ensure_one()
                table.add_qty(orderpoint.id, purchase_info, pol.product_uom_qty)

            # create a record per po picking
            if purchase_info.at_finish():
                for picking in po.picking_ids.filtered(lambda x: x.state != 'cancel'):
                    moves, kit_moves = self._get_valid_moves(picking, orderpoint_products)
                    if not moves and not kit_moves:
                        continue

                    purchase_info = PurchaseInfo.create('PO', po, picking.scheduled_date)
                    table.append_purchase_info(purchase_info)

                    for move in moves:
                        orderpoint = orderpoints.filtered(lambda x: x.product_id == move.product_id)[:1].ensure_one()
                        table.add_qty(orderpoint.id, purchase_info, self._get_qty_from_move(move))

                    if kit_moves:
                        for pol, move_iter in groupby(kit_moves, lambda x: x.purchase_line_id):
                            moves = list(move_iter)

                            orderpoint = orderpoints.filtered(lambda x: x.product_id == pol.product_id)[:1].ensure_one()
                            table.add_qty(orderpoint.id, purchase_info, self._get_qty_from_kit_moves(pol, moves))

    def _get_valid_moves(self, picking, orderpoint_products):
        moves = self._env['stock.move']
        kit_moves = self._env['stock.move']

        for move in picking.move_lines:
            bom = move.bom_line_id.bom_id
            if bom and bom.type == 'phantom':
                product = bom.product_id
                product_tmpl = bom.product_tmpl_id

                fst = bom.product_id and product in orderpoint_products
                snd = not bom.product_id and product_tmpl in orderpoint_products.mapped('product_tmpl_id')
                if fst or snd:
                    kit_moves |= move
            elif move.product_id in orderpoint_products:
                moves |= move

        return moves, kit_moves

    def _get_qty_from_move(self, move):
        total = 0.0

        def _convert_qty(move):
            return move.product_uom._compute_quantity(move.product_uom_qty, move.product_id.uom_po_id)

        # a copy from purchase_stock / purchase.order.line:_compute_qty_received()
        if move.location_dest_id.usage == "supplier":
            if move.to_refund:
                total -= _convert_qty(move)
        elif move.origin_returned_move_id and move.origin_returned_move_id._is_dropshipped() and not move._is_dropshipped_returned():
            # Edge case: the dropship is returned to the stock, no to the supplier.
            # In this case, the received quantity on the PO is set although we didn't
            # receive the product physically in our stock. To avoid counting the
            # quantity twice, we do nothing.
            pass
        elif (
            move.location_dest_id.usage == "internal"
            and move.to_refund
            and move.location_dest_id
            not in self._env["stock.location"].search(
                [("id", "child_of", move.warehouse_id.view_location_id.id)]
            )
        ):
            total -= _convert_qty(move)
        else:
            total += _convert_qty(move)

        return total

    def _get_qty_from_kit_moves(self, pol, moves):
        component_info = {}

        MrpBom = self._env['mrp.bom'].sudo()
        bom = MrpBom._bom_find(product=pol.product_id, company_id=pol.company_id.id, bom_type='phantom')
        bom.ensure_one()

        for bom_line, info in bom.explode(bom.product_id, 1)[1]:
            rounding = bom_line.product_uom_id.rounding

            has_zero_qty = float_is_zero(bom_line.product_qty, precision_rounding=rounding)
            if has_zero_qty or bom_line.product_id.type not in ('product', 'consu'):
                continue

            component_info[bom_line.product_id.id] = 0.0

        for move in moves:
            move_qty = self._get_qty_from_move(move)

            has_zero_qty = float_is_zero(move_qty, precision_rounding=move.product_id.uom_po_id.rounding)
            if has_zero_qty:
                continue

            bom_line = move.bom_line_id.ensure_one()
            product_purchase_uom = move.product_id.uom_po_id.ensure_one()
            bom_line_qty = bom_line.product_uom_id._compute_quantity(bom_line.product_qty, product_purchase_uom)

            component_info[move.product_id.id] += move_qty // (bom_line_qty or 1)

        return min(component_info.values())
