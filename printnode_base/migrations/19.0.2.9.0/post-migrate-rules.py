from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    _migrate_user_rules(env)
    _migrate_report_policies(env)


def _migrate_user_rules(env):
    user_rules = env['printnode.rule'].with_context(
        active_test=False,
    ).search([])

    for user_rule in user_rules:
        env['printnode.print.rule'].create({
            'sequence': 1,
            'active': user_rule.active,
            'user_id': user_rule.user_id.id,
            'report_id': user_rule.report_id.id,
            'printer_id': user_rule.printer_id.id,
            'printer_bin': user_rule.printer_bin.id,
        })

    user_rules.write({
        'active': False,
    })


def _migrate_report_policies(env):
    report_policies = env['printnode.report.policy'].search([
        ('active', '=', True),
    ])

    for report_policy in report_policies:
        # Skip policies that have no printing action.
        if (
            not report_policy.printer_id
            and not report_policy.exclude_from_auto_printing
        ):
            continue

        env['printnode.print.rule'].create({
            'sequence': 2,
            'active': True,
            'report_id': report_policy.report_id.id,
            'printer_id': report_policy.printer_id.id,
            'printer_bin': report_policy.printer_bin.id,
            'report_paper_id': report_policy.report_paper_id.id,
            'exclude_from_auto_printing': report_policy.exclude_from_auto_printing,
        })

    report_policies.write({
        'active': False,
    })
