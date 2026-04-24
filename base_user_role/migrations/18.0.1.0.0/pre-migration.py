# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)

MODULES = [
    "rma",
    "account_journal_general_sequence",
    "hr_holidays_public",
    "hr_attendance_report_theoretical_time",
    "efarmer_activities",
    "efarmer_bom_disassembly",
    "efarmer_forecasted_receipts_report",
    "efarmer_helpdesk_repair",
    "efarmer_sale_customer_mail",
    "efarmer_sale_report",
    "hr_attendance_autoclose",
    "hr_attendance_calendar_view",
    "hr_attendance_geolocation",
    "hr_attendance_reason",
    "hr_attendance_report_theoretical_time",
    "hr_holidays_public",
    "list_view_sticky_header",
    "purchase_invoice_plan",
    "purchase_open_qty",
    "purchase_order_line_sequence",
    "sale_order_line_sequence",
    "stock_picking_line_sequence",
    "sale_delivery_state",
]

ACTION_MODELS = [
    ("ir.actions.act_window", "ir_act_window"),
    ("ir.actions.server", "ir_act_server"),
    ("ir.actions.report", "ir_act_report_xml"),
    ("ir.actions.client", "ir_act_client"),
    ("ir.actions.act_url", "ir_act_url"),
]

def delete_by_model(cr, model, table):
    _logger.info(f"🧹 Deleting {model} from table {table}")

    # Check table exists first
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = %s
        )
    """, (table,))
    if not cr.fetchone()[0]:
        _logger.warning(f"  Table {table} does not exist, skipping")
        return

    try:
        cr.execute(f"""
            DELETE FROM {table}
            WHERE id IN (
                SELECT res_id
                FROM ir_model_data
                WHERE module = ANY(%s)
                  AND model = %s
            )
        """, (MODULES, model))
        _logger.info(f"  Deleted {cr.rowcount} records from {table}")
    except Exception as e:
        _logger.error(f"Failed deleting {model}: {e}")
        cr.execute("ROLLBACK TO SAVEPOINT delete_savepoint")

def delete_views_recursive(cr, modules):
    """
    Delete views registered by modules recursively.
    First collects ALL child views (at any depth) that inherit
    from views being deleted, then deletes all of them together.
    This avoids the ir_ui_view_inheritance_mode constraint
    which forbids extension views from having inherit_id = NULL.
    """
    _logger.info("🧹 Collecting views to delete (including all children)...")

    # Get initial set of view ids from our modules
    cr.execute("""
        SELECT res_id
        FROM ir_model_data
        WHERE module = ANY(%s)
        AND model = 'ir.ui.view'
        AND EXISTS (
            SELECT 1 FROM ir_ui_view WHERE id = res_id
        )
    """, (modules,))

    initial_ids = set(row[0] for row in cr.fetchall())
    if not initial_ids:
        _logger.info("  No views found, skipping")
        return

    _logger.info(f"  Found {len(initial_ids)} direct views from modules")

    # Recursively collect ALL child views at any depth
    all_ids = set(initial_ids)
    current_level = set(initial_ids)

    depth = 0
    while current_level:
        depth += 1
        cr.execute("""
            SELECT id
            FROM ir_ui_view
            WHERE inherit_id = ANY(%s)
            AND id != ANY(%s)
        """, (list(current_level), list(all_ids)))

        children = set(row[0] for row in cr.fetchall())
        if not children:
            break

        _logger.info(f"  Found {len(children)} child views at depth {depth}")
        all_ids.update(children)
        current_level = children

    _logger.info(f"  Total views to delete (including children): {len(all_ids)}")

    # Delete all collected views in one query
    try:
        cr.execute("""
            DELETE FROM ir_ui_view
            WHERE id = ANY(%s)
        """, (list(all_ids),))
        _logger.info(f"  ✅ Deleted {cr.rowcount} views")
    except Exception as e:
        _logger.error(f"  Failed deleting views: {e}")
        cr.execute("ROLLBACK TO SAVEPOINT delete_savepoint")


def delete_menus_recursive(cr, modules):
    """
    Delete menus registered by modules recursively.
    First collects ALL child menus at any depth,
    then clears action references and deletes all at once.
    """
    _logger.info("🧹 Collecting menus to delete (including all children)...")

    cr.execute("""
        SELECT res_id
        FROM ir_model_data
        WHERE module = ANY(%s)
        AND model = 'ir.ui.menu'
        AND EXISTS (
            SELECT 1 FROM ir_ui_menu WHERE id = res_id
        )
    """, (modules,))

    initial_ids = set(row[0] for row in cr.fetchall())
    if not initial_ids:
        _logger.info("  No menus found, skipping")
        return

    _logger.info(f"  Found {len(initial_ids)} direct menus from modules")

    # Recursively collect ALL child menus at any depth
    all_ids = set(initial_ids)
    current_level = set(initial_ids)

    depth = 0
    while current_level:
        depth += 1
        cr.execute("""
            SELECT id
            FROM ir_ui_menu
            WHERE parent_id = ANY(%s)
            AND id != ANY(%s)
        """, (list(current_level), list(all_ids)))

        children = set(row[0] for row in cr.fetchall())
        if not children:
            break

        _logger.info(f"  Found {len(children)} child menus at depth {depth}")
        all_ids.update(children)
        current_level = children

    _logger.info(f"  Total menus to delete (including children): {len(all_ids)}")

    # Clear action references first to avoid FK issues
    try:
        cr.execute("""
            UPDATE ir_ui_menu
            SET action = NULL
            WHERE id = ANY(%s)
        """, (list(all_ids),))
        _logger.info(f"  Cleared action references from {cr.rowcount} menus")
    except Exception as e:
        _logger.error(f"  Failed clearing menu actions: {e}")
        cr.execute("ROLLBACK TO SAVEPOINT delete_savepoint")
        return

    # Delete all collected menus in one query
    try:
        cr.execute("""
            DELETE FROM ir_ui_menu
            WHERE id = ANY(%s)
        """, (list(all_ids),))
        _logger.info(f"  ✅ Deleted {cr.rowcount} menus")
    except Exception as e:
        _logger.error(f"  Failed deleting menus: {e}")
        cr.execute("ROLLBACK TO SAVEPOINT delete_savepoint")

def clean_specific_views(cr):
    """
    Clean specific views that have orphaned action references
    stored in DB from V15 that conflict with V18 file versions.
    """
    _logger.info("🧹 Cleaning specific orphaned DB view content...")

    import json
    import re

    # View 4721 has x_wl_action_validate_bank_account button
    # stored in DB from V15 trilab_whitelist module
    orphaned_buttons = [
        "x_wl_action_validate_bank_account",
    ]

    for button_name in orphaned_buttons:
        cr.execute("""
            SELECT id, arch_db
            FROM ir_ui_view
            WHERE arch_db::text ILIKE %s
        """, (f"%{button_name}%",))

        rows = cr.fetchall()
        if not rows:
            _logger.info(f"  No views found with button {button_name}, skipping")
            continue

        pattern = re.compile(
            rf'<button[^>]*name="{re.escape(button_name)}"[^>]*/>'
            rf'|<button[^>]*name="{re.escape(button_name)}"[^>]*>.*?</button>',
            re.I | re.S
        )

        for view_id, arch_db in rows:
            try:
                if isinstance(arch_db, dict):
                    cleaned_arch = {}
                    for lang, content in arch_db.items():
                        cleaned_arch[lang] = pattern.sub("", content)
                    cr.execute("""
                        UPDATE ir_ui_view
                        SET arch_db = %s::jsonb
                        WHERE id = %s
                    """, (json.dumps(cleaned_arch), view_id))

                elif isinstance(arch_db, str):
                    try:
                        parsed = json.loads(arch_db)
                        if isinstance(parsed, dict):
                            cleaned_arch = {}
                            for lang, content in parsed.items():
                                cleaned_arch[lang] = pattern.sub("", content)
                            cr.execute("""
                                UPDATE ir_ui_view
                                SET arch_db = %s::jsonb
                                WHERE id = %s
                            """, (json.dumps(cleaned_arch), view_id))
                        else:
                            cleaned = pattern.sub("", arch_db)
                            cr.execute("""
                                UPDATE ir_ui_view
                                SET arch_db = %s
                                WHERE id = %s
                            """, (cleaned, view_id))
                    except (json.JSONDecodeError, TypeError):
                        cleaned = pattern.sub("", arch_db)
                        cr.execute("""
                            UPDATE ir_ui_view
                            SET arch_db = %s
                            WHERE id = %s
                        """, (cleaned, view_id))

                _logger.info(f"  ✅ Cleaned button {button_name} from view id={view_id}")

            except Exception as e:
                _logger.warning(f"  ⚠️ Failed to clean view id={view_id}: {e}")

def migrate(cr, version):
    if not version:
        return

    _logger.info("START CLEANUP (SAFE MODE)")
    clean_specific_views(cr)
    
    # =====================================================
    # CLEAN CONFIG PARAMETERS (avoid duplicate key error)
    # =====================================================
    _logger.info("Cleaning ir.config_parameter duplicates")

    params = [
        ("integration.import_data_block_size", "5000"),
        ("integration.export_inventory_block_size", "250"),
        ("integration.integration_api_key", "8c60bb92a2a7beb2a0fc399f0831d6d818a87441"),
        ("vt_ecosystem.ecosystem_api_url", "https://ecosystem-api.ventor.tech/v1"),
        ("integration.skip_convert_to_webp", "0"),
    ]

    keys = [key for key, value in params]
    placeholders = ','.join(['%s'] * len(keys))
    cr.execute(f"""
        DELETE FROM ir_config_parameter
        WHERE key IN ({placeholders})
    """, tuple(keys))
    _logger.info(f"  Deleted {cr.rowcount} config param records")

    # =====================================================
    # DELETE IN STRICT ORDER (FK SAFE)
    # =====================================================

    # 1. Delete all action types first
    # (menus reference actions, so actions must go first)
    for model, table in ACTION_MODELS:
        cr.execute("SAVEPOINT delete_savepoint")
        delete_by_model(cr, model, table)

    # 2. Delete menus recursively
    # (collect children first, clear actions, then delete)
    cr.execute("SAVEPOINT delete_savepoint")
    delete_menus_recursive(cr, MODULES)

    # 3. Delete views recursively
    # (collect all children at any depth, then delete all at once
    #  to avoid ir_ui_view_inheritance_mode constraint violation)
    cr.execute("SAVEPOINT delete_savepoint")
    delete_views_recursive(cr, MODULES)

    # 4. Delete mail templates
    cr.execute("SAVEPOINT delete_savepoint")
    delete_by_model(cr, "mail.template", "mail_template")

    # =====================================================
    # CLEAN ir_model_data LAST
    # Must be last — everything above relies on it
    # to find records to delete
    # =====================================================
    _logger.info("🧹 Cleaning ir_model_data")
    try:
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE module = ANY(%s)
        """, (MODULES,))
        _logger.info(f"  Deleted {cr.rowcount} ir_model_data records")
    except Exception as e:
        _logger.error(f"Failed cleaning ir_model_data: {e}")

    _logger.info("✅ CLEANUP FINISHED")

# # -*- coding: utf-8 -*-

# import logging

# _logger = logging.getLogger(__name__)


# def _delete_ir_model_data(cr, module, xml_id, model):
#     cr.execute("""
#         DELETE FROM ir_ui_view
#         WHERE id IN (
#             SELECT res_id
#             FROM ir_model_data
#             WHERE module = %s
#               AND name = %s
#               AND model = %s
#         )
#     """, (module, xml_id, model))


# def migrate(cr, version):
#     if not version:
#         return

#     _logger.info("Starting Odoo 18 metadata cleanup")

#     # =====================================================
#     # 1. VIEWS
#     # =====================================================
#     views_to_delete = [
#         ("efarmer_activities", "mail_activity_view_kanban"),
#         ("efarmer_activities", "efarmer_mail_activity_view_search_inherit"),
#         ("efarmer_activities", "efarmer_mail_activity_view_tree_inherit"),
#         ("efarmer_bom_disassembly", "mrp_bom_form_view"),
#         ("efarmer_forecasted_receipts_report", "view_partner_stock_form"),
#         ("efarmer_helpdesk_repair", "helpdesk_ticket_view_form_inherit_helpdesk_stock"),
#         ("efarmer_helpdesk_repair", "res_config_settings_view_form"),
#         ("efarmer_helpdesk_repair", "stock_warehouse_lot_prefix_view_tree"),
#         ("efarmer_helpdesk_repair", "res_config_settings_view_form"),
#         ("efarmer_helpdesk_repair", "efarmer_helpdesk_repair_view_form"),
#         ("efarmer_sale_report", "efarmer_sale_report_view_tree"),
#         ("efarmer_sale_report", "efarmer_sale_report_view_search"),
#         ("efarmer_trilab_extension", "efarmer_trilab_view_order_form_inherit"),
#         ("efarmer_whitelist_history", "view_move_whitelist_history_form_inherit"),
#         ("efarmer_whitelist_history", "view_whitelist_history_form"),
#         ("efarmer_whitelist_history", "view_whitelist_history_tree"),
#         ("efarmer_whitelist_history", "view_whitelist_history_search"),
#         ("hr_attendance_autoclose", "hr_attendance_view_form"),
#         ("hr_attendance_autoclose", "view_attendance_tree"),
#         ("hr_attendance_autoclose", "view_employee_form_inherit_hr_attendance"),
#         ("hr_attendance_autoclose", "res_config_settings_view_form"),
#         ("hr_attendance_autoclose", "res_config_settings_view_form"),
#         ("hr_attendance_calendar_view", "view_attendance_calendar"),
#         ("hr_attendance_geolocation", "hr_attendance_view_form"),
#         ("hr_attendance_geolocation", "view_attendance_tree"),
#         ("hr_attendance_reason", "hr_attendance_reason_view_form"),
#         ("hr_attendance_reason", "hr_attendance_reason_view_tree"),
#         ("hr_attendance_reason", "hr_attendance_view_form"),
#         ("hr_attendance_reason", "hr_attendance_view_tree"),
#         ("hr_attendance_reason", "res_config_settings_view_form"),
#         ("hr_attendance_report_theoretical_time", "hr_attendance_view_pivot"),
#         ("hr_attendance_report_theoretical_time", "hr_attendance_theoretical_view_filter"),
#         ("hr_attendance_report_theoretical_time", "hr_attendance_theoretical_view_pivot"),
#         ("hr_attendance_report_theoretical_time", "hr_attendance_theoretical_view_graph"),
#         ("hr_attendance_report_theoretical_time", "view_employee_form_inherit_hr_attendance"),
#         ("hr_attendance_report_theoretical_time", "edit_holiday_status_form"),
#         ("hr_attendance_report_theoretical_time", "recompute_theoretical_attendance_form"),
#         ("hr_attendance_report_theoretical_time", "wizard_theoretical_time_form_view"),
#         ("hr_holidays_public", "view_holidays_public_tree"),
#         ("hr_holidays_public", "view_holidays_public_form"),
#         ("hr_holidays_public", "edit_holiday_status_form"),
#         ("hr_holidays_public", "holidays_public_next_year_wizard_view"),
#         ("purchase_invoice_plan", "view_purchase_invoice_plan_tree"),
#         ("purchase_invoice_plan", "view_purchase_invoice_plan_form"),
#         ("purchase_invoice_plan", "purchase_order_form"),
#         ("purchase_invoice_plan", "view_purchase_invoice_plan_filter"),
#         ("purchase_invoice_plan", "view_purchase_invoice_plan_tree_readonly"),
#         ("purchase_invoice_plan", "view_purchase_create_invoice_plan"),
#         ("purchase_invoice_plan", "view_purchase_make_planned_invoice"),
#         ("purchase_open_qty", "purchase_order_form"),
#         ("purchase_open_qty", "view_purchase_order_line_tree"),
#         ("purchase_open_qty", "view_purchase_order_filter"),
#         ("purchase_open_qty", "purchase_order_line_search"),
#         ("purchase_order_line_sequence", "view_move_form"),
#         ("purchase_order_line_sequence", "purchase_order_line_form"),
#         ("purchase_order_line_sequence", "purchase_order_form"),
#         ("rma", "res_config_settings_view_form"),
#         ("rma", "view_partner_form"),
#         ("rma", "rma_finalization_view_search"),
#         ("rma", "view_rma_finalization_form"),
#         ("rma", "view_rma_finalization_list"),
#         ("rma", "rma_tag_view_search"),
#         ("rma", "view_rma_tag_form"),
#         ("rma", "view_rma_tag_list"),
#         ("rma", "rma_team_view_tree"),
#         ("rma", "rma_team_view_form"),
#         ("rma", "rma_view_search"),
#         ("rma", "rma_view_tree"),
#         ("rma", "rma_view_form"),
#         ("rma", "rma_finalization_form"),
#         ("rma", "rma_view_pivot"),
#         ("rma", "rma_view_calendar"),
        
#     ]

#     for module, xml_id in views_to_delete:
#         _logger.info("Deleting view %s.%s", module, xml_id)
#         cr.execute("""
#             DELETE FROM ir_ui_view
#             WHERE id IN (
#                 SELECT res_id
#                 FROM ir_model_data
#                 WHERE module = %s
#                   AND name = %s
#                   AND model = 'ir.ui.view'
#             )
#         """, (module, xml_id))

#     # =====================================================
#     # 2. ACTIONS (ir.actions.act_window)
#     # =====================================================
#     actions_to_delete = [
#         ("efarmer_activities", "efarmer_action_mail_activity"),
#         ("efarmer_activities", "mail_activity_action_view_form"),
#         ("efarmer_activities", "mail_activity_action_view_tree"),
#         ("efarmer_activities", "mail_activity_action_view_kanban"),
#         ("efarmer_helpdesk_repair", "stock_warehouse_lot_prefix_action"),
#         ("efarmer_helpdesk_repair", "efarmer_helpdesk_repair_action_view_form"),
#         ("efarmer_sale_report", "efarmer_sale_report_action_view_form"),
#         ("efarmer_whitelist_history", "action_view_whitelist_history"),
#         ("hr_attendance_reason", "hr_attendance_reason_action"),
#         ("hr_attendance_report_theoretical_time", "hr_attendance_theoretical_action"),
#         ("hr_attendance_report_theoretical_time", "recompute_employee_theoretical_attendance"),
#         ("hr_attendance_report_theoretical_time", "act_wizard_recompute_theoretical_attendance"),
#         ("hr_attendance_report_theoretical_time", "wizard_theoretical_time_act_window"),
#         ("hr_holidays_public", "open_holidays_public_view"),
#         ("hr_holidays_public", "action_create_next_year_public_holidays"),
#         ("purchase_invoice_plan", "action_purchase_invoice_plan"),
#         ("purchase_invoice_plan", "action_purchase_create_invoice_plan"),
#         ("purchase_invoice_plan", "action_view_purchase_make_planned_invoice"),
#         ("rma", "action_rma_finalization"),
#         ("rma", "action_rma_tag"),
#         ("rma", "rma_team_action"),
#         ("rma", "rma_action"),
#     ]

#     for module, xml_id in actions_to_delete:
#         _logger.info("Deleting action %s.%s", module, xml_id)
#         cr.execute("""
#             DELETE FROM ir_actions_act_window
#             WHERE id IN (
#                 SELECT res_id
#                 FROM ir_model_data
#                 WHERE module = %s
#                   AND name = %s
#                   AND model = 'ir.actions.act_window'
#             )
#         """, (module, xml_id))

#     # =====================================================
#     # 3. MENUS (ir.ui.menu)
#     # =====================================================
#     menus_to_delete = [
#         ("efarmer_activities", "menu_mail_activity_root"),
#         ("efarmer_activities", "efarmer_action_mail_activity"),
#         ("efarmer_helpdesk_repair", "stock_warehouse_lot_prefix_action"),
#         ("efarmer_sale_report", "efarmer_sale_report_menu"),
#         ("efarmer_whitelist_history", "menu_action_whitelist_history"),
#         ("hr_attendance_reason", "hr_attendance_settings_redefinition_menu"),
#         ("hr_attendance_reason", "hr_attendance_reason_menu"),
#         ("hr_attendance_report_theoretical_time", "menu_hr_attendance_report"),
#         ("hr_attendance_report_theoretical_time", "menu_hr_attendance_theoretical_root"),
#         ("hr_attendance_report_theoretical_time", "menu_hr_attendance_theoretical_report"),
#         ("hr_attendance_report_theoretical_time", "act_wizard_recompute_theoretical_attendance"),
#         ("hr_attendance_report_theoretical_time", "menu_hr_attendance_theoretical_report_select"),
#         ("hr_holidays_public", "menu_hr_public_holidays"),
#         ("hr_holidays_public", "menu_holidays_public_view"),
#         ("hr_holidays_public", "menu_create_next_year_public_holidays"),
#         ("purchase_invoice_plan", "menu_purchase_invoice_plan"),
#         ("rma", "rma_menu"),
#         ("rma", "rma_orders_menu"),
#         ("rma", "rma_reporting_menu"),
#         ("rma", "rma_configuration_menu"),
#         ("rma", "rma_configuration_rma_finalization_menu"),
#         ("rma", "rma_configuration_rma_tag_menu"),
#         ("rma", "rma_configuration_rma_team_menu"),
#         ("rma", "rma_orders_menu"),
#     ]

#     for module, xml_id in menus_to_delete:
#         _logger.info("Deleting menu %s.%s", module, xml_id)
#         cr.execute("""
#             DELETE FROM ir_ui_menu
#             WHERE id IN (
#                 SELECT res_id
#                 FROM ir_model_data
#                 WHERE module = %s
#                   AND name = %s
#                   AND model = 'ir.ui.menu'
#             )
#         """, (module, xml_id))

#     # 4.

#     templates_to_delete = [
#         ("efarmer_sale_customer_mail", "mail_template_sale_payment_confirmation"),
#         ("mail_template_data_portal_reminder", "mail_template_sale_payment_confirmation"),
#         ("purchase_order_line_sequence", "report_invoice_document_inherit_purchase_sequence"),
#         ("purchase_order_line_sequence", "report_purchase_order_sequence_qweb"),
#         ("purchase_order_line_sequence", "report_purchase_quote_sequence_qweb"),
#         ("rma", "report_rma_document"),
#         ("rma", "report_rma"),
#         ("rma", "portal_my_home_menu_rma"),
#         ("rma", "portal_my_home_rma"),
#         ("rma", "portal_my_rmas"),
#         ("rma", "portal_rma_page"),
#     ]

#     for module, xml_id in templates_to_delete:
#         cr.execute("""
#             DELETE FROM mail_template
#             WHERE id IN (
#                 SELECT res_id
#                 FROM ir_model_data
#                 WHERE module = %s
#                 AND name = %s
#                 AND model = 'mail.template'
#             )
#         """, (module, xml_id))

#     # 5.
#     server_actions_to_delete = [
#         ("efarmer_whitelist_history", "efarmer_action_check_partner_whitelist"),
#         ("rma", "rma_refund_action_server"),
#     ]
#     for module, xml_id in server_actions_to_delete:
#         cr.execute("""
#             DELETE FROM ir_actions_server
#             WHERE id IN (
#                 SELECT res_id
#                 FROM ir_model_data
#                 WHERE module = %s
#                 AND name = %s
#                 AND model = 'ir.actions.server'
#             )
#         """, (module, xml_id))

#     # 6.
#     report_actions_to_delete = [
#         ("rma", "report_rma_action"),
#     ]

#     for module, xml_id in report_actions_to_delete:
#         cr.execute("""
#             DELETE FROM ir_actions_report
#             WHERE id IN (
#                 SELECT res_id
#                 FROM ir_model_data
#                 WHERE module = %s
#                 AND name = %s
#                 AND model = 'ir.actions.report'
#             )
#         """, (module, xml_id))

#     _logger.info("Metadata cleanup finished")
