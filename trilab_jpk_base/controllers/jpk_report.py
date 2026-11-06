import json
import logging
from urllib.parse import parse_qsl, urlparse

from odoo.addons.web.controllers.report import ReportController
from odoo.http import content_disposition, request, route
from odoo.http import serialize_exception as _serialize_exception
from odoo.tools import html_escape
from odoo.tools.safe_eval import safe_eval, time

_logger = logging.getLogger(__name__)

JPK_RENDER_METHODS = {
    'jpk_xlsx': '_render_jpk_xlsx',
    'jpk_xml': '_render_jpk_xml',
}

CONTENT_TYPES = {
    'jpk_xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'jpk_xml': 'text/xml',
}


class JpkReportController(ReportController):
    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        if converter in JPK_RENDER_METHODS:
            context = dict(request.env.context)

            if docids:
                docids = [int(docid) for docid in docids.split(',')]

            if _options := data.pop('options', None):
                data |= json.loads(_options)

            if _context := data.pop('context', None):
                data['context'] = json.loads(_context)
                context |= data['context']

            _data = getattr(
                request.env['ir.actions.report']._get_report_from_name(reportname).with_context(**context),
                JPK_RENDER_METHODS[converter],
            )(reportname, docids, data=data)[0]

            return request.make_response(
                _data,
                headers=[
                    ('Content-Type', CONTENT_TYPES[converter]),
                    ('Content-Length', len(_data)),
                ],
            )

        return super().report_routes(reportname, docids, converter, **data)

    @route()
    def report_download(self, data, context=None, token=None):
        request_content = json.loads(data)
        url, report_type = request_content[0], request_content[1]

        if report_type.startswith('jpk_'):
            report_name = None

            try:
                report_name = url.split(f'/report/{report_type}/')[1].split('?')[0]
                docids = None

                if '/' in report_name:
                    report_name, docids = report_name.split('/')

                report = request.env['ir.actions.report']._get_report_from_name(report_name)
                extension = report_type.removeprefix('jpk_')
                filename = f'{report.name}.{extension}'

                if docids:
                    response = self.report_routes(report_name, docids=docids, converter=report_type, context=context)

                    obj = request.env[report.model].browse([int(docid) for docid in docids.split(',')])

                    if report.print_report_name and not len(obj) > 1:
                        filename = f'{safe_eval(report.print_report_name, {"object": obj, "time": time})}.{extension}'

                else:
                    url_data = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))

                    if 'context' in url_data:
                        context = json.dumps(json.loads(context or '{}') | json.loads(url_data.pop('context')))

                    response = self.report_routes(report_name, converter=report_type, context=context, **url_data)

                if not response.headers.get('Content-Disposition'):
                    response.headers.add('Content-Disposition', content_disposition(filename))

                return response

            except Exception as error:
                _logger.exception(f'Cannot generate report {report_name}')

                return request.make_response(
                    html_escape(
                        json.dumps({'code': 200, 'message': 'Odoo Server Error', 'data': _serialize_exception(error)})
                    )
                )

        return super().report_download(data, context=context, token=token)
