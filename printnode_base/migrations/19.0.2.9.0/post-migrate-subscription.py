from odoo import api, SUPERUSER_ID


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
