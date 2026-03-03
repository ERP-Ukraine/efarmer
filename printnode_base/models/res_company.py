# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


REPORT_DOMAIN = [
    '|', ('model', '=', 'product.product'), ('model', '=', 'product.template'),
    ('report_type', 'in', ['qweb-pdf', 'qweb-text', 'py3o']),
    ('report_name', '!=', 'product.report_pricelist'),
]


class Company(models.Model):
    _inherit = 'res.company'

    printnode_enabled = fields.Boolean(
        string='Enable Printing for Company',
        default=False,
    )

    printnode_printer = fields.Many2one(
        'printnode.printer',
        string='Default Printer',
    )

    print_labels_format = fields.Selection(
        [
            ('dymo', 'Dymo'),
            ('2x7xprice', '2 x 7 with price'),
            ('4x7xprice', '4 x 7 with price'),
            ('4x12', '4 x 12'),
            ('4x12xprice', '4 x 12 with price'),
            ('zpl', 'ZPL Labels'),
            ('zplxprice', 'ZPL Labels with price')
        ],
        string="Default Product Labels Format",
        help='Set default label printing format')

    printnode_recheck = fields.Boolean(
        string='Mandatory check Printing Status',
        default=False,
        help='If this checkbox is set the printer status is verified'
             'when documents are set in printing Wizard',
    )

    printnode_account_id = fields.Many2one(
        comodel_name='printnode.account',
        compute='_compute_printnode_account_id',
        readonly=True,
    )

    company_label_printer = fields.Many2one(
        'printnode.printer',
        string='Default Shipping Label Printer',
    )

    company_sl_keyword = fields.Char(
        string='Keyword',
    )

    auto_send_slp = fields.Boolean(
        string='Automatically Print Shipping Labels',
        default=False,
    )

    print_sl_from_attachment = fields.Boolean(
        string='Enable Fallback Attachment Search',
        default=False,
    )

    print_sl_by_keyword = fields.Boolean(
        string='Shipping Label Search Keyword',
        default=False,
    )

    im_a_teapot = fields.Boolean(
        string='Show success notifications',
        default=True,
        help='Shows message that report was successfully sent to Direct Print service',
    )

    print_package_with_label = fields.Boolean(
        string='Print Package Label Immediately After Shipping Label',
        default=False,
    )

    printnode_package_report = fields.Many2one(
        'ir.actions.report',
        string='Package Report to Print',
    )

    scales_enabled = fields.Boolean(
        string='Enable Scales Integration',
        default=False,
    )

    printnode_scales = fields.Many2one(
        'printnode.scales',
        string='Default Scales',
    )

    scales_picking_domain = fields.Char(
        string='Picking criteria for auto-weighing',
        default='[["picking_type_code","=","outgoing"]]'
    )

    printnode_notification_email = fields.Char(
        string="Direct Print Notification Email",
    )

    printnode_notification_page_limit = fields.Integer(
        string="Direct Print Notification Page Limit",
        default=100,
    )

    printnode_fit_to_page = fields.Boolean(
        string='Disable fit to the page size',
        default=False,
        help='Set this checkbox to disable automatic scaling of the document to fit the page',
    )

    debug_logging = fields.Boolean(
        string='Requests Debug logging',
        default=False,
        help='By enabling this feature, all requests will be logged',
    )

    log_type_ids = fields.Many2many(
        comodel_name='printnode.log.type',
        string='Logs to write',
        required=False,
    )

    printing_scenarios_from_crons = fields.Boolean(
        string='Allow to execute printing scenarios from crons',
        default=True,
        help='Set this checkbox to allow to execute printing scenarios from crons',
    )

    secure_printing = fields.Boolean(
        string='Printing without sending documents to the print server',
        default=False,
        help='This checkbox will enable Secure Printing Mode. In this mode, instead of sending '
             'the document\'s content to print, the print server receives a special download link '
             'for the document. This link is then passed to the client application, which downloads '
             'the document and sends it to print. This means that your documents content is never '
             'sent to the Direct Print server.',
    )

    prevent_duplicate_printing = fields.Boolean(
        string='Prevent duplicate printing',
        default=True,
        help='Prevent dublicate printing',
    )

    def _compute_printnode_account_id(self):
        account = self.env['printnode.account'].get_main_printnode_account()
        for company in self:
            company.printnode_account_id = account

    @api.onchange('auto_send_slp')
    def _onchange_auto_send_slp(self):
        if not self.auto_send_slp:
            self.print_sl_by_keyword = False

    @api.onchange('debug_logging', 'log_type_ids')
    def _check_debug_logging(self):
        if not self.debug_logging:
            self.log_type_ids = [(5, 0, 0)]
        elif not self.log_type_ids:
            log_types = self.env[self.log_type_ids._name].search([('active', '=', True)])
            self.log_type_ids = [(4, log_type.id) for log_type in log_types]

    @api.onchange('print_package_with_label', 'print_sl_from_attachment')
    def _onchange_print_package_with_label(self):
        if self.print_package_with_label:
            self.print_sl_from_attachment = False

            group_settings = self.env['res.config.settings'].default_get(
                ['group_stock_tracking_lot']
            )
            if not group_settings.get('group_stock_tracking_lot'):
                self.print_package_with_label = False
                return {
                    "warning": {
                        "title": _("Configuration Error"),
                        "message": _(
                            "This setting cannot be enabled. "
                            "Please enable the use of Packages in Odoo settings."
                        ),
                    }
                }
        if self.print_sl_from_attachment:
            self.print_package_with_label = False
