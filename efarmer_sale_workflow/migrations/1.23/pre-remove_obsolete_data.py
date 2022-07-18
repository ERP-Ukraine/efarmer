import logging

from odoo import SUPERUSER_ID, api

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def delete_records_safely_by_xml_id(env, xml_ids):
    """This removes in the safest possible way the records whose XML-IDs are
    passed as argument.
    :param xml_ids: List of XML-ID string identifiers of the records to remove.
    """
    IMD = env['ir.model.data'].with_context(active_test=False, _force_unlink=True)
    for xml_id in xml_ids:
        logger.debug('Deleting record for XML-ID %s', xml_id)
        try:
            with env.cr.savepoint():
                view = IMD.xmlid_to_object(xml_id, raise_if_not_found=False)
                if view:
                    view.unlink()
        except Exception as e:
            logger.error('Error deleting XML-ID %s: %s', xml_id, repr(e))

def remove_fields(cr):
    cr.execute("""
        DELETE FROM ir_model_data
             WHERE model='ir.model.fields'
             AND module='efarmer_sale_workflow'
             AND name in (
	            'field_ir_actions_server_activity_record'
            )
    """)

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, dict())
    remove_fields(cr)
    delete_records_safely_by_xml_id(env, [
        'efarmer_sale_workflow.assets_backend',
        'efarmer_sale_workflow.report_assets_common',
        'efarmer_sale_workflow.external_layout_clean',
        'efarmer_sale_workflow.view_invoice_tree',
        'efarmer_sale_workflow.efarmer_sale_workflow_mail_view_server_action_form_template',
    ])
