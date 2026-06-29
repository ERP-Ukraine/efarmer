from datetime import datetime, timezone

from odoo import api, fields, models
from odoo.modules.registry import Registry

from ..utils_pdf import generate_pdf_from_zpl


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    zld_label_ids = fields.One2many(
        comodel_name='zld.label',
        inverse_name='action_report_id',
        string='ZPL Label Designer Labels',
        readonly=True,
    )

    @property
    def zld_label_id(self):
        """
        Return the first (and typically only) associated ZPL label.
        """
        self.ensure_one()
        return self.zld_label_ids[:1] if self.zld_label_ids else self.env['zld.label']

    @api.model
    def _render_qweb_text(self, docids, data=None):
        """
        :rtype: bytes
        """
        if data and data.get('is_zld_product_label', False):
            docids = self._get_docids_for_zld_product_label(data)

        return super()._render_qweb_text(docids, data)

    def _get_docids_for_zld_product_label(self, data):
        """
        This method add records to use in the report based on the active_model and quantity from
        the wizard.
        """
        docids = []
        quantity_by_product = data.get('quantity_by_product', {})
        for p, q in quantity_by_product.items():
            docids += [int(p) for i in range(q)]

        custom_barcodes = data.get('custom_barcodes', {})
        for barcode, qty in custom_barcodes.items():
            docids += [docids[0]] * sum(qty.values())

        return docids

    def _generate_pdf_from_zpl_label(self, res_ids=None, data=None):
        """
        Generate PDF content from ZPL label using Labelary API.

        This method handles the complete flow:
        1. Gets the associated ZPL label
        2. Renders ZPL content
        3. Gets label parameters (width, height, DPI)
        4. Converts ZPL to PDF via Labelary API
        5. Tracks the request in the daily counter (in a proper transaction)

        :param res_ids: List of record IDs to render, or None
        :param data: Optional dictionary with report data
        :return: PDF content as bytes
        :raises: ValueError if no associated label found or convert_to_pdf is disabled
        """
        self.ensure_one()

        label = self.zld_label_id
        if not label:
            raise ValueError("No associated ZPL label found for this report")

        if not label.convert_to_pdf:
            raise ValueError("PDF conversion is not enabled for this label")

        # Render ZPL content
        # Use report_name instead of xml_id for consistency
        zpl_content = self._render_qweb_text(
            res_ids, data=data)[0]

        # Get label parameters
        width_in = label.width
        height_in = label.height

        # Convert DPI to dpmm format (DPI / 25.4, since 1 inch = 25.4mm)
        # Labelary API expects dpmm as a string like '8dpmm', '12dpmm', etc.
        dpi_value = label.dpi
        dpmm_value = round(dpi_value / 25.4)
        dpmm = f'{dpmm_value}dpmm'

        # Convert ZPL to PDF using Labelary API
        # For proper page sizing: when all_labels=True and no page_layout is set,
        # Labelary creates PDF pages matching the label dimensions exactly.
        try:
            pdf_content, _total_count, _headers = generate_pdf_from_zpl(
                zpl=zpl_content,
                dpmm=dpmm,
                width_in=width_in,
                height_in=height_in,
                all_labels=True,
                # Explicitly set page_size to None to use label dimensions as page size
                # page_layout should also be None to avoid forcing a grid layout
            )
        finally:
            # Increment daily request counter in a proper transaction
            # This happens in finally block to track all API requests, even if they fail
            self._increment_labelary_request_counter()

        return pdf_content

    def _increment_labelary_request_counter(self):
        """
        Increment the daily Labelary API request counter (resets at midnight UTC).

        Uses a separate cursor to ensure the counter is saved even if the main
        transaction fails, since the API request has already been sent.
        """
        try:
            # Get database name from current cursor
            dbname = self.env.cr.dbname
            uid = self.env.uid
            context = self.env.context

            # Use a separate cursor to ensure counter is saved independently
            registry = Registry(dbname)
            with registry.cursor() as new_cr:
                new_env = api.Environment(new_cr, uid, context)

                # Check if counter needs to be reset (at midnight UTC)
                last_reset_date_str = new_env['ir.config_parameter'].sudo().get_param(
                    'zpl_label_designer_pdf.labelary_requests_last_reset_date'
                )

                # Get current UTC date
                current_utc_date = datetime.now(timezone.utc).date()

                should_reset = False
                if last_reset_date_str:
                    try:
                        last_reset_date = datetime.fromisoformat(last_reset_date_str).date()
                        # If last reset was not today (UTC), reset the counter
                        if last_reset_date < current_utc_date:
                            should_reset = True
                    except (ValueError, TypeError):
                        # Invalid date format, reset everything
                        should_reset = True
                else:
                    # First time, initialize with current date
                    should_reset = False  # Don't reset, just set the date

                if should_reset:
                    # Reset counter and update last reset date
                    new_env['ir.config_parameter'].sudo().set_param(
                        'zpl_label_designer_pdf.labelary_requests_today', '0'
                    )
                    new_env['ir.config_parameter'].sudo().set_param(
                        'zpl_label_designer_pdf.labelary_requests_last_reset_date',
                        current_utc_date.isoformat()
                    )
                    current_count = 0
                else:
                    # Initialize last reset date if not set
                    if not last_reset_date_str:
                        new_env['ir.config_parameter'].sudo().set_param(
                            'zpl_label_designer_pdf.labelary_requests_last_reset_date',
                            current_utc_date.isoformat()
                        )

                    # Get current count
                    current_count_str = new_env['ir.config_parameter'].sudo().get_param(
                        'zpl_label_designer_pdf.labelary_requests_today', '0'
                    )
                    try:
                        current_count = int(current_count_str)
                    except (ValueError, TypeError):
                        current_count = 0

                # Increment counter
                new_count = current_count + 1
                new_env['ir.config_parameter'].sudo().set_param(
                    'zpl_label_designer_pdf.labelary_requests_today', str(new_count)
                )

                # Commit is automatic when exiting the cursor context manager
        except Exception:
            # Silently fail - counter is not critical functionality
            pass

