import base64
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PrintNodePrinter(models.Model):
    _inherit = 'printnode.printer'

    def printnode_print(self, report_id, objects, copies=1, options=None, data=None, postcommit=True):
        """
        Override to convert ZPL to PDF when convert_to_pdf is enabled.
        """
        # Check if this is a ZPL label report that needs PDF conversion
        report_id.ensure_one()

        label = report_id.zld_label_id
        if not label or not label.convert_to_pdf:
            return super().printnode_print(
                report_id, objects,
                copies=copies,
                options=options,
                data=data,
                postcommit=postcommit,
            )

        # Perform printer check (same as original printnode_print)
        self.printnode_check_report(report_id)

        try:
            ids = objects and objects.mapped('id') or None
            pdf_content = report_id._generate_pdf_from_zpl_label(res_ids=ids, data=data)

            # Prepare printjob data with PDF content
            printjob_data = {
                'printerId': self.printnode_id,
                'title': self._format_title(objects, copies),
                'source': self._get_source_name(),
                'contentType': 'raw_base64',
                'content': base64.b64encode(pdf_content).decode('ascii'),
                'qty': copies,
                'options': self._get_data_options(options),
            }

            res = self._post_printnode_job(printjob_data)

            # If model has printnode_printed flag and this flag is not inherited from other model
            # (through _inherits) mark records as printed
            if (
                'printnode_printed' in objects._fields
                and not objects._fields['printnode_printed'].inherited
            ):
                objects.write({
                    'printnode_printed': True,
                })

            return res

        except Exception as e:
            _logger.warning(
                "Failed to convert ZPL to PDF for label %s (ID: %s). "
                "Falling back to original ZPL format. Error: %s",
                label.name,
                label.id,
                str(e),
                exc_info=True
            )

        # Fall back to original behavior if PDF conversion fails
        # Continue with the original method implementation
        return super().printnode_print(
            report_id,
            objects,
            copies=copies,
            options=options,
            data=data,
            postcommit=postcommit,
        )
