import json
import logging
from urllib.parse import parse_qsl, urlparse

from odoo.addons.web.controllers.report import ReportController
from odoo.http import content_disposition, request, route
from odoo.http import serialize_exception as _serialize_exception
from odoo.tools import html_escape
from odoo.tools.safe_eval import safe_eval, time

_logger = logging.getLogger(__name__)


class JpkReportController(ReportController):
    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        if converter == 'jpk_xlsx':
            report = request.env['ir.actions.report']._get_report_from_name(reportname)
            context = dict(request.env.context)

            if docids:
                docids = [int(i) for i in docids.split(',')]

            if data.get('options'):
                data.update(json.loads(data.pop('options')))

            if data.get('context'):
                data['context'] = json.loads(data['context'])
                context.update(data['context'])

            xlsx = report.with_context(**context)._render_jpk_xlsx(reportname, docids, data=data)[0]
            xlsxhttpheaders = [
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Length', len(xlsx)),
            ]

            return request.make_response(xlsx, headers=xlsxhttpheaders)

        elif converter == 'jpk_xml':
            report = request.env['ir.actions.report']._get_report_from_name(reportname)
            context = dict(request.env.context)

            if docids:
                docids = [int(i) for i in docids.split(',')]

            if data.get('options'):
                data.update(json.loads(data.pop('options')))

            if data.get('context'):
                data['context'] = json.loads(data['context'])
                context.update(data['context'])

            xml = report.with_context(**context)._render_jpk_xml(reportname, docids, data=data)[0]
            httpheaders = [('Content-Type', 'text/xml'), ('Content-Length', len(xml))]
            return request.make_response(xml, headers=httpheaders)

        return super().report_routes(reportname, docids, converter, **data)

    @route()
    def report_download(self, data, context=None, token=None):
        request_content = json.loads(data)
        url, report_type = request_content[0], request_content[1]

        if report_type.startswith('jpk_'):
            reportname = None

            try:
                reportname = url.split(f'/report/{report_type}/')[1].split('?')[0]
                docids = None

                if '/' in reportname:
                    reportname, docids = reportname.split('/')

                if docids:
                    # Generic report:
                    response = self.report_routes(reportname, docids=docids, converter=report_type, context=context)

                else:
                    # Particular report:
                    data = dict(
                        parse_qsl(urlparse(url).query, keep_blank_values=True)
                    )  # decoding the args represented in JSON
                    if 'context' in data:
                        context = json.dumps(json.loads(context or '{}') | json.loads(data.pop('context')))
                    response = self.report_routes(reportname, converter=report_type, context=context, **data)

                report = request.env['ir.actions.report']._get_report_from_name(reportname)
                extension = report_type.removeprefix('jpk_')
                filename = f'{report.name}.{extension}'

                if docids:
                    ids = [int(x) for x in docids.split(',')]
                    obj = request.env[report.model].browse(ids)

                    if report.print_report_name and not len(obj) > 1:
                        report_name = safe_eval(report.print_report_name, {'object': obj, 'time': time})
                        filename = f'{report_name}.{extension}'

                if not response.headers.get('Content-Disposition'):
                    response.headers.add('Content-Disposition', content_disposition(filename))

                return response

            except Exception as e:
                _logger.exception('Error while generating report %s', reportname)
                se = _serialize_exception(e)
                error = {'code': 200, 'message': 'Odoo Server Error', 'data': se}
                return request.make_response(html_escape(json.dumps(error)))

        else:
            return super().report_download(data, context=context, token=token)
