import logging

_logger = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def migrate(cr, installed_version):
    _logger.info(f'Start migration 15.0.96.0.0 from {installed_version}')

    with cr.savepoint():
        cr.execute("""UPDATE jpk_vat_7m
                      SET document_type_id = (SELECT res_id
                                              FROM ir_model_data
                                              WHERE name = CASE version
                                                               WHEN '1-0E' THEN 'jpk_v7m_1_0_doc_type'
                                                               WHEN '1-2E' THEN 'jpk_v7m_1_2_doc_type'
                                                  END)
                      WHERE document_type_id IS NULL
                        AND version IN ('1-0E', '1-2E');""")


    _logger.info('End migration 16.0.96.0.0')
