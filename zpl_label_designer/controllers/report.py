import logging
import json
import werkzeug.exceptions

from werkzeug.urls import url_parse

from odoo import http
from odoo.http import content_disposition, request
from odoo.tools.misc import html_escape
from odoo.tools.safe_eval import safe_eval, time

from odoo.addons.web.controllers.main import ReportController


_logger = logging.getLogger(__name__)


class ReportController(ReportController):
    @http.route(['/report/download'], type='http', auth="user")
    # pylint: disable=unused-argument
    def report_download(self, data, context=None):
        """
        TODO: Add docstring
        """
        requestcontent = json.loads(data)
        url, type_ = requestcontent[0], requestcontent[1]
        reportname = '???'
        try:
            if type_ in ['qweb-pdf', 'qweb-text']:
                pattern = '/report/pdf/' if type_ == 'qweb-pdf' else '/report/text/'
                reportname = url.split(pattern)[1].split('?')[0]

                docids = None
                if '/' in reportname:
                    reportname_, docids = reportname.split('/')
                else:
                    reportname_ = reportname

                report = request.env['ir.actions.report']._get_report_from_name(reportname_)

                # Check if there's an associated zld.label for this report
                # If not, use the default report routes
                label = report.zld_label_id
                if not report.zld_label_id or not label.convert_to_pdf:
                    return super().report_download(data, context)

                # Generate PDF using Labelary API
                extension = 'pdf'
                pdf_content = None
                if docids:
                    # Generic report:
                    pdf_content = self._generate_pdf_for_zpl_report(label, reportname_, docids, context=context)
                else:
                    # Particular report:
                    data = url_parse(url).decode_query(cls=dict)
                    if 'context' in data:
                        context, data_context = json.loads(context or '{}'), json.loads(data.pop('context'))
                        context = json.dumps({**context, **data_context})

                    pdf_content = self._generate_pdf_for_zpl_report(label, reportname_, docids, context=context, **data)

                report = request.env['ir.actions.report']._get_report_from_name(reportname_)
                filename = "%s.%s" % (report.name, extension)

                if docids:
                    ids = [int(x) for x in docids.split(",") if x.isdigit()]
                    obj = request.env[report.model].browse(ids)
                    if report.print_report_name and not len(obj) > 1:
                        report_name = safe_eval(report.print_report_name, {'object': obj, 'time': time})
                        filename = "%s.%s" % (report_name, extension)

                pdf_headers = [
                    ('Content-Type', 'application/pdf'),
                    ('Content-Length', len(pdf_content)),
                    ('Content-Disposition', content_disposition(filename)),
                ]
                return request.make_response(pdf_content, headers=pdf_headers)
            else:
                return

        except Exception as e:
            _logger.warning("Error while generating report %s", reportname, exc_info=True)

            se = http.serialize_exception(e)
            error = {
                'code': 200,
                'message': "Odoo Server Error",
                'data': se
            }

            res = request.make_response(html_escape(json.dumps(error)))

            raise werkzeug.exceptions.InternalServerError(response=res) from e

    def _generate_pdf_for_zpl_report(self, label, reportname, docids=None, **data):
        """
        Generate PDF for ZPL report using the centralized method in ir.actions.report.
        """
        context = dict(request.env.context)

        if docids:
            docids = [int(i) for i in docids.split(',') if i.isdigit()]
        if data.get('options'):
            data.update(json.loads(data.pop('options')))
        if data.get('context'):
            data['context'] = json.loads(data['context'])
            context.update(data['context'])

        # Get the report record and use the centralized PDF generation method
        report = request.env['ir.actions.report'].with_context(context)._get_report_from_name(reportname)
        pdf = report._generate_pdf_from_zpl_label(res_ids=docids, data=data)

        return pdf
