import io
import enum
import base64
import logging
import operator
import datetime
from itertools import groupby
from datetime import timedelta
from collections import defaultdict

from xlsxwriter.utility import xl_rowcol_to_cell

from odoo import api, fields
from odoo.exceptions import UserError
from odoo.tools import PatchedXlsxWorkbook, float_is_zero

def get_week_no(date):
    return date.isocalendar()[1]

class BackgroundColor(enum.Enum):
    DEFAULT = '#ffffff'
    GREEN = '#b7d8a9'
    GREY = '#efefef'
    RED = '#e34138'
    RFQ = '#fbd965'
    PO = '#94c57e'

class OrderpointInfo:

    def __init__(self, orderpoint):
        product = orderpoint.product_id
        now = fields.Datetime.now()

        self.orderpoint = orderpoint
        self.product_categ = product.categ_id.display_name

        self.code = product.default_code or ''
        self.product_name = product.name
        self.min_qty = orderpoint.product_min_qty
        self.max_qty = orderpoint.product_max_qty
        self.lead_time = self.map_sellers_to_lead_time(product.seller_ids)
        self.avail_qty = product.qty_available
        self.forecasted_qty = product.virtual_available
        self.avail_to_promise = self.get_avail_to_promise(product, now)
        self.avail_to_promise_next_week = self.get_avail_to_promise_next_week(product, now)

    def get_columns(self):
        return (
            ('code', self.code),
            ('product_name', self.product_name),
            ('min_qty', self.min_qty),
            ('max_qty', self.max_qty),
            ('lead_time', self.lead_time),
            ('avail_qty', self.avail_qty),
            ('forecasted_qty', self.forecasted_qty),
            ('avail_to_promise', self.avail_to_promise),
            ('avail_to_promise_next_week', self.avail_to_promise_next_week),
        )

    @property
    def rowspan(self):
        return len(self.lead_time) or 1

    @classmethod
    def make_fake_orderpoint(cls, kit_orderpoint, component):
        """Mock orderpoint with a component data."""
        now = fields.Datetime.now()

        orderpoint_info = cls(kit_orderpoint)
        orderpoint_info.code = component.default_code or ''
        orderpoint_info.product_name = component.name
        orderpoint_info.min_qty = 0
        orderpoint_info.max_qty = 0
        orderpoint_info.lead_time = cls.map_sellers_to_lead_time([])
        orderpoint_info.avail_qty = component.qty_available
        orderpoint_info.forecasted_qty = component.virtual_available
        orderpoint_info.avail_to_promise = cls.get_avail_to_promise(component, now)
        orderpoint_info.avail_to_promise_next_week = cls.get_avail_to_promise_next_week(component, now)
        return orderpoint_info

    @staticmethod
    def map_sellers_to_lead_time(sellers):
        if len(sellers) > 1:
            return sellers.mapped(lambda x: '{} days - {}'.format(x.delay, x.name.display_name or ''))
        elif sellers:
            return [str(sellers.delay) + ' days']
        else:
            return []

    @staticmethod
    def get_avail_to_promise(product, now):
        """
        Available to Promise = (
            остатки на складе на момент выгрузки - резерв + запланированные поступления -
            запланированные отгрузки на момент выгрузки отчета.
        )
        """
        product = product.with_context(to_date=now)
        return product.virtual_available

    @staticmethod
    def get_avail_to_promise_next_week(product, now):
        """
        Available to Promise + 1 week = (
            остатки на складе на момент выгрузки - резерв + запланированные поступления -
            запланированные отгрузки  на момент выгрзки отчета + 1 неделя
        )
        """
        to_date = now + timedelta(days=7)
        product = product.with_context(to_date=to_date)
        return product.virtual_available

class BOMInfo:

    def  __init__(self, bom, product, kit_orderpoint, orderpoints):
        self.bom = bom
        self.product = product
        self.lines = self._make_lines(kit_orderpoint, orderpoints)

    def __hash__(self):
        return hash(self.bom)

    def __eq__(self, other):
        return operator.eq(self.bom, other.bom)

    def _make_lines(self, kit_orderpoint, orderpoints):
        res = []

        picking_type = self.bom.picking_type_id
        lines = self.bom.sudo().explode(self.product, 1, picking_type=picking_type)[1]
        for bom_line, info in lines:
            component = bom_line.product_id
            orderpoint = orderpoints.filtered(lambda x: x.product_id == component)[:1]

            if orderpoint:
                data = OrderpointInfo(orderpoint)
                data.orderpoint = kit_orderpoint
            else:
                data = OrderpointInfo.make_fake_orderpoint(kit_orderpoint, component)

            res.append((component, data))

        return res

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
        week_no = get_week_no(date)
        return cls(code, title_tmpl.format(code=code, po=po, date=date), date, week_no, po.state)

    def at_finish(self):
        return self.state in ('purchase', 'done')

    def at_start(self):
        return self.state in ('draft', 'sent', 'to approve')

class WorksheetSetRowParams:

    def __init__(self, row, height, cell_format, options):
        self.unpack_me = (row, height, cell_format, options)

class WorksheetFormulaParams:

    def __init__(self, row, height, formula):
        self.unpack_me = (row, height, formula)

class TableCell:

    def __init__(self, row_no, col_no, rowspan, colspan, value, format):
        self.row_no = row_no
        self.col_no = col_no
        self.rowspan = rowspan
        self.colspan = colspan
        self.value = value
        self.format = format

class Table:

    def __init__(self, workbook):
        self._workbook = workbook

        self._orderpoints = []
        self._red_orderpoint_ids = set()

        self._orderpoints_to_bom_map = defaultdict(set)

        self._purchases = []
        self._quantities = defaultdict(float)
        self._cell_formats = {}

        self.fold_groups = []  # append WorksheetSetRowParams objects here
        self.formulas = []  # append WorksheetFormulaParams objects here

    def append_orderpoint_info(self, record):
        self._orderpoints.append(record)

    def append_bom_info(self, orderpoint_id, data):
        self._orderpoints_to_bom_map[orderpoint_id].add(data)

    def append_purchase_info(self, data):
        if isinstance(data, list):
            self._purchases.extend(data)
        else:
            self._purchases.append(data)

    def add_qty(self, orderpoint_id, purchase_info, qty, bom_id=False, product_id=False):
        if purchase_info.at_start():
            self._red_orderpoint_ids.add(orderpoint_id)
        self._quantities[(orderpoint_id, purchase_info, bom_id, product_id)] += qty

    def get_cell_format(self, font_size=10, bg_color=BackgroundColor.DEFAULT, align='left', valign='vcenter', bold=False, text_wrap=False, rotation=0):
        args = (font_size, bg_color, align, valign, bold, text_wrap, rotation)

        if args in self._cell_formats:
            return self._cell_formats[args]

        wb_format = self._workbook.add_format({
            'font_name': 'Arial',
            'font_size': font_size,
            'text_wrap': text_wrap,
            'rotation': rotation,
            'bold': bold,
            'border': True,
            'align': align,
            'valign': valign,
            'bg_color': bg_color.value,
        })
        self._cell_formats[args] = wb_format
        return wb_format

    def get_frezee_col_count(self):
        return len(self._get_orderpoints_titles())

    def __iter__(self):
        # orderpoints titles
        orderpoints_titles = self._get_orderpoints_titles()
        for col_no, title in enumerate(orderpoints_titles):
            cell_format = self.get_cell_format(font_size=12, align='center', valign='bottom', text_wrap=True, bold=True, bg_color=BackgroundColor.GREEN)
            yield TableCell(0, col_no, 2, 1, title, cell_format)

        # rfq / po titles

        ordered_purchase_info = []
        col_no = len(orderpoints_titles)
        for week_no, purchases in groupby(sorted(self._purchases, key=lambda x: x.date), key=lambda x: x.week_no):
            purchases = list(purchases)
            col_width = len(purchases)

            cell_format = self.get_cell_format(font_size=12, align='center', text_wrap=True, bold=True)
            yield TableCell(0, col_no, 1, col_width, 'week {:02d}'.format(week_no), cell_format)
            ordered_purchase_info.extend(purchases)
            col_no += col_width

        for col_no, purchase_info in enumerate(ordered_purchase_info, start=len(orderpoints_titles)):
            bg_color = BackgroundColor.RFQ if purchase_info.code == 'RFQ' else BackgroundColor.PO
            cell_format = self.get_cell_format(font_size=12, align='center', text_wrap=True, rotation=90, bg_color=bg_color)
            yield TableCell(1, col_no, 1, 1, purchase_info.title, cell_format)

        # other rows

        def fill_line(orderpoint_info, bom_id=False, product_id=False, bold=False):
            nonlocal row_no
            orderpoint_id = orderpoint_info.orderpoint.id

            # This field is an array and there should be the one value per row,
            # but at least one row must exist.
            rowspan = orderpoint_info.rowspan

            for col_no, (field, value) in enumerate(orderpoint_info.get_columns()):
                cell_format = self._get_orderpoint_cell_format(orderpoint_info, field, bold=bold)
                if field == 'lead_time':
                    for i in range(rowspan):
                        # If there is no vendors, no TableCell record is yield.
                        # But it causes a problem with red rows.
                        value_ = '' if len(orderpoint_info.lead_time) <= i else value[i]
                        yield TableCell(row_no+i, col_no, 1, 1, value_, cell_format)
                else:
                    yield TableCell(row_no, col_no, rowspan, 1, value, cell_format)

            for col_no, purchase_info in enumerate(ordered_purchase_info, start=len(orderpoints_titles)):
                cell_format = self._get_qty_cell_format(orderpoint_info, purchase_info, bold=bold)
                qty = self._quantities.get((orderpoint_id, purchase_info, bom_id, product_id), '')
                yield TableCell(row_no, col_no, rowspan, 1, qty, cell_format)

            row_no += rowspan

        row_no = 2
        for categ, records in groupby(sorted(self._orderpoints, key=lambda x: x.product_categ), key=lambda x: x.product_categ):
            categ_row_no = row_no
            product_rows_numbers = []

            # fill the categ row later
            row_no += 1

            for orderpoint_info in records:
                bom_info_records = self._orderpoints_to_bom_map.get(orderpoint_info.orderpoint.id)
                is_kit = bool(bom_info_records)

                product_rows_numbers.append(row_no)
                yield from fill_line(orderpoint_info, bold=is_kit)

                if is_kit:
                    for bom_info in bom_info_records:
                        for component, orderpoint_info in bom_info.lines:
                            rowspan = orderpoint_info.rowspan
                            self.fold_groups.extend(WorksheetSetRowParams(row_no+i, None, None, {'level': 2, 'hidden': True}) for i in range(rowspan))
                            yield from fill_line(orderpoint_info, bom_id=bom_info.bom.id, product_id=component.id)

            # the categ name
            cell_format = self.get_cell_format(bold=True)
            yield TableCell(categ_row_no, 0, 1, 5, categ, cell_format)

            # the avail qty column
            value = '=SUM({})'.format(','.join(xl_rowcol_to_cell(x, 5) for x in product_rows_numbers))
            self.formulas.append(WorksheetFormulaParams(categ_row_no, 5, value))

            # the forecasted qty column
            value = '=SUM({})'.format(','.join(xl_rowcol_to_cell(x, 6) for x in product_rows_numbers))
            self.formulas.append(WorksheetFormulaParams(categ_row_no, 6, value))

            # the 'avail to promise' qty column
            value = '=SUM({})'.format(','.join(xl_rowcol_to_cell(x, 7) for x in product_rows_numbers))
            self.formulas.append(WorksheetFormulaParams(categ_row_no, 7, value))

            # the 'avail to promise + 1 week' qty column
            value = '=SUM({})'.format(','.join(xl_rowcol_to_cell(x, 8) for x in product_rows_numbers))
            self.formulas.append(WorksheetFormulaParams(categ_row_no, 8, value))

            # RFQ / PO columns
            start = len(orderpoints_titles)
            end = start + len(ordered_purchase_info)
            for col_no in range(start, end):
                value = '=SUM({})'.format(','.join(xl_rowcol_to_cell(x, col_no) for x in product_rows_numbers))
                self.formulas.append(WorksheetFormulaParams(categ_row_no, col_no, value))

            self.fold_groups.extend(WorksheetSetRowParams(i, None, None, {'level': 1, 'hidden': True}) for i in range(categ_row_no+1, row_no))

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
            'Available to Promise',
            'Available to Promise + 1 week',
        )

    def _is_red_row(self, orderpoint_info):
        return any((
            orderpoint_info.forecasted_qty < 0,
            orderpoint_info.orderpoint.id in self._red_orderpoint_ids,
        ))

    def _get_orderpoint_cell_format(self, orderpoint_info, field, bold=False):
        bg_color = (BackgroundColor.RED if self._is_red_row(orderpoint_info) else
                    BackgroundColor.GREY if field == 'lead_time' else
                    BackgroundColor.DEFAULT)
        align = 'left' if field in ('code', 'product_name') else 'center'
        return self.get_cell_format(bg_color=bg_color, align=align, bold=bold)

    def _get_qty_cell_format(self, orderpoint_info, purchase_info, bold=False):
        bg_color = (BackgroundColor.RED if self._is_red_row(orderpoint_info) else
                    BackgroundColor.RFQ if purchase_info.code == 'RFQ' else
                    BackgroundColor.PO)
        return self.get_cell_format(bg_color=bg_color, align='center', bold=bold)

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

        stream = io.BytesIO()
        with PatchedXlsxWorkbook(stream) as workbook:
            table = Table(workbook)
            self._put_orderpoints_to_table(orderpoints, table)
            self._put_purchases_to_table(orderpoints, table)

            worksheet = workbook.add_worksheet()

            worksheet.set_row(1, 150)
            worksheet.set_column(0, 0, 25)
            worksheet.set_column(1, 1, 35)
            worksheet.set_column(2, 2, 12)
            worksheet.set_column(3, 3, 12)
            worksheet.set_column(4, 4, 25)
            worksheet.set_column(5, 5, 15)
            worksheet.set_column(6, 6, 15)
            worksheet.set_column(7, 7, 15)
            worksheet.set_column(8, 8, 15)

            for cell in table:
                if cell.rowspan > 1 or cell.colspan > 1:
                    x1, y1  = cell.row_no, cell.col_no
                    x2, y2 = cell.row_no + cell.rowspan - 1, cell.col_no + cell.colspan - 1
                    worksheet.merge_range(x1, y1, x2, y2, cell.value, cell.format)
                else:
                    worksheet.write(cell.row_no, cell.col_no, cell.value, cell.format)

            formula_format = workbook.add_format({
                'font_name': 'Arial',
                'font_size': 10,
                'align': 'center',
                'valign': 'vcenter',
                'border': True,
                'bold': True,
            })
            for params in table.formulas:
                worksheet.write_formula(*params.unpack_me, cell_format=formula_format)

            for params in reversed(table.fold_groups):
                worksheet.set_row(*params.unpack_me)

            worksheet.freeze_panes(2, table.get_frezee_col_count())

        stream.seek(0)
        return stream

    def _put_orderpoints_to_table(self, orderpoints, table):
        for orderpoint in orderpoints:
            # Append an orderpoint row.
            table.append_orderpoint_info(OrderpointInfo(orderpoint))

            # Append a component row if it exists.
            product = orderpoint.product_id
            bom = self._env['mrp.bom'].sudo()._bom_find(product=product, company_id=orderpoint.company_id.id, bom_type='phantom')
            if bom:
                bom_info = BOMInfo(bom, product, orderpoint, orderpoints)
                table.append_bom_info(orderpoint.id, bom_info)

    def _put_purchases_to_table(self, orderpoints, table):
        orderpoint_products = orderpoints.mapped('product_id')

        for po in self._env['purchase.order'].sudo().search([('state', '!=', 'cancel')]):
            valid_po_lines = po.order_line.filtered(lambda x: x.product_id in orderpoint_products)

            if po.is_all_delivered() or not valid_po_lines:
                continue

            # create a record from the RFQ
            purchase_info = PurchaseInfo.create('RFQ', po, po.date_order)
            table.append_purchase_info(purchase_info)

            for pol in valid_po_lines:
                product = pol.product_id
                orderpoint = orderpoints.filtered(lambda x: x.product_id == product)[:1].ensure_one()

                bom = self._env['mrp.bom'].sudo()._bom_find(product=product, company_id=pol.company_id.id, bom_type='phantom')
                if bom:
                    bom_info = BOMInfo(bom, product, orderpoint, orderpoints)
                    table.append_bom_info(orderpoint.id, bom_info)

                    # append the kit qty
                    table.add_qty(orderpoint.id, purchase_info, pol.product_uom_qty)

                    # append the kit components qty
                    boms, lines = bom.sudo().explode(product, pol.product_uom_qty, picking_type=bom.picking_type_id)
                    for bom_line, info in lines:
                        table.add_qty(orderpoint.id, purchase_info, info['qty'], bom_id=bom.id, product_id=bom_line.product_id.id)
                else:
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

                            bom = self._env['mrp.bom'].sudo()._bom_find(product=pol.product_id, company_id=pol.company_id.id, bom_type='phantom')
                            bom.ensure_one()
                            for move in moves:
                                product = move.product_id

                                bom_info = BOMInfo(bom, product, orderpoint, orderpoints)
                                table.append_bom_info(orderpoint.id, bom_info)

                                table.add_qty(orderpoint.id, purchase_info, self._get_qty_from_move(move), bom_id=bom.id, product_id=product.id)

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
