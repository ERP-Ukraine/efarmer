import logging

from odoo import SUPERUSER_ID, api

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def delete_records_safely_by_xml_id(env, xml_ids):
    """This removes in the safest possible way the records whose XML-IDs are
    passed as argument.
    :param xml_ids: List of XML-ID string identifiers of the records to remove.
    """
    for xml_id in xml_ids:
        logger.debug('Deleting record for XML-ID %s', xml_id)
        try:
            with env.cr.savepoint():
                view = env['ir.ui.view'].search([('key', '=', xml_id)]).exists()
                if view:
                    view.unlink()
        except Exception as e:
            logger.error('Error deleting XML-ID %s: %s', xml_id, repr(e))

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, dict())
    delete_records_safely_by_xml_id(env, [
        'efarmer_sale_workflow.proforma_external_layout_clean',
        'efarmer_sale_workflow.proforma_address_layout',
    ])
