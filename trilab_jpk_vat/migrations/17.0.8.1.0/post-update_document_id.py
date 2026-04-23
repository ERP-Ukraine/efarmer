import logging

_logger = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def migrate(cr, version):
    _logger.info(f'Start migration 17.0.8.1.0 from {version}')

    with cr.savepoint():
        cr.execute("""UPDATE jpk_vat_7m
         SET document_type_id = (SELECT res_id FROM ir_model_data WHERE name = 'jpk_v7m_1_2_doc_type')
         WHERE document_type_id IS NULL""")

        cr.execute("""UPDATE jpk_vat_ue
         SET document_type_id = (SELECT res_id FROM ir_model_data WHERE name = 'vat_ue5_v2_0e_doc_type')
         WHERE document_type_id IS NULL""")

    _logger.info(f'End migration 17.0.8.1.0')
