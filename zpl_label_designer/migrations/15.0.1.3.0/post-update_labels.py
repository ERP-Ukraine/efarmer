# Copyright 2023 VentorTech OU
# See LICENSE file for full copyright and licensing details.
import re

from odoo import api, SUPERUSER_ID


PLACEHOLDER_REGEX = r'\%\%[a-z_\d\.]+?\%\%'
FIELD_PLACEHOLDER = '<t t-esc="doc.{}"/>'
TEMPLATE_BASE = '<t t-foreach="docs" t-as="doc">{content}</t>'
SPECIAL_CHARACTERS = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
}


def prepare_label_template(zpl):
    # Replace placeholders with qweb fields
    label_content = zpl

    # Replace special characters in placeholders with html entities
    for char, replacement in SPECIAL_CHARACTERS.items():
        label_content = label_content.replace(char, replacement)

    placeholders = re.findall(PLACEHOLDER_REGEX, label_content)

    for placeholder in placeholders:
        placeholder_attr = placeholder[2:-2]  # Remove %% from start and end
        placeholder_value = FIELD_PLACEHOLDER.format(placeholder_attr)

        label_content = label_content.replace(placeholder, placeholder_value)

    template = TEMPLATE_BASE.format(content=label_content)

    return template


def publish(label):
    """
    Simplified copy of publish method from version 1.2.0
    """
    view_xmlid = f'zpl_label_designer.{label.model_id.model.replace(".", "_")}_label_{label.id}'
    label_view_id = label.env['ir.ui.view'].create({
        'type': 'qweb',
        'arch': prepare_label_template(label.zpl),
        'name': view_xmlid,
        'key': view_xmlid
    })
    label.env['ir.model.data'].create({
        'module': 'zpl_label_designer',
        'name': view_xmlid,
        'model': 'ir.ui.view',
        'res_id': label_view_id.id,
        # Make it no updatable to avoid deletion on module upgrade
        'noupdate': True,
    })

    label.view_id = label_view_id

    action_xmlid = f'zpl_label_designer.{label.model_id.model.replace(".", "_")}_label_action_{label.id}'  # NOQA
    label_action_report = label.env['ir.actions.report'].create({
        'xml_id': action_xmlid,
        'name': label.name,
        'model': label.model_id.model,
        'report_type': 'qweb-text',
        'report_name': view_xmlid,
        'report_file': view_xmlid,
        'print_report_name': label.print_report_name or f"'{label.name}'",
        'binding_model_id': label.model_id.id,
        'binding_type': 'report',
    })
    label.env['ir.model.data'].create({
        'module': 'zpl_label_designer',
        'name': action_xmlid,
        'model': 'ir.actions.report',
        'res_id': label_action_report.id,
        # Make it no updatable to avoid deletion on module upgrade
        'noupdate': True,
    })

    label.action_report_id = label_action_report
    label.is_published = True

    return True


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    labels = env['zld.label'].search([['is_published', '=', False]])

    for label in labels:
        # Publish using old logic
        publish(label)

        # Unpublish using new logic
        label.unpublish()
