import logging

from odoo import api, SUPERUSER_ID


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    old_cron_xml_ids = [
        'printnode_base.printnode_limits_update_action',
        'printnode_base.printnode_releases_update_action',
        'printnode_base.printnode_clean_printjob_action',
    ]

    for xml_id in old_cron_xml_ids:
        cron = env.ref(xml_id, raise_if_not_found=False)
        if cron:
            cron.action_archive()

    try:
        with env.cr.savepoint():
            env['printnode.account'].update_subscription_info()
    except Exception as error:
        _logger.exception(
            'Failed to update Direct Print subscription info during migration: %s',
            error,
        )
