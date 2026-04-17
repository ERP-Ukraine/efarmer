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
    "trilab_jpk_vat",
    "trilab_pl_reports",
    "trilab_whitelist-15.0.2.5",
    "trilab_ksef",
    "trilab_invoice",
    "trilab_jpk_base",
    "efarmer_trilab_extension",
    "efarmer_whitelist_history",
    "integration",
]

def delete_by_model(cr, model, table):
    _logger.info(f"🧹 Deleting {model}")

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
    except Exception as e:
        _logger.error(f"Failed deleting {model}: {e}")
        cr.rollback()

def migrate(cr, version):
    if not version:
        return

    _logger.info("START CLEANUP (SAFE MODE)")

    # =====================================================
    # DELETE IN STRICT ORDER (FK SAFE)
    # =====================================================

    # 1. action views
    delete_by_model(cr, "ir.actions.act_window.view", "ir_actions_act_window_view")

    # 2. server actions
    delete_by_model(cr, "ir.actions.server", "ir_actions_server")

    # 3. report actions
    delete_by_model(cr, "ir.actions.report", "ir_actions_report")

    # 4. window actions
    delete_by_model(cr, "ir.actions.act_window", "ir_actions_act_window")

    # 5. menus (AFTER actions!)
    delete_by_model(cr, "ir.ui.menu", "ir_ui_menu")

    # 6. views
    delete_by_model(cr, "ir.ui.view", "ir_ui_view")

    # 7. mail templates
    delete_by_model(cr, "mail.template", "mail_template")

    # =====================================================
    # OPTIONAL: your custom data models
    # =====================================================
    # Example:
    # delete_by_model(cr, "account.account.tag", "account_account_tag")
    # delete_by_model(cr, "jpk.account.tag", "jpk_account_tag")

    # =====================================================
    # CLEAN ir_model_data LAST
    # =====================================================
    _logger.info("Cleaning ir_model_data")

    try:
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE module = ANY(%s)
        """, (MODULES,))
    except Exception as e:
        _logger.error(f"Failed cleaning ir_model_data: {e}")
        cr.rollback()

    # =====================================================
    # CLEAN CONFIG PARAMETERS (avoid duplicate key error)
    # =====================================================
    _logger.info("Cleaning ir.config_parameter duplicates")

    config_keys_to_delete = [
        "integration.import_data_block_size",
    ]

    for key in config_keys_to_delete:
        try:
            cr.execute("""
                DELETE FROM ir_config_parameter
                WHERE key = %s
            """, (key,))
        except Exception as e:
            _logger.error(f"Failed deleting config param {key}: {e}")
            cr.rollback()
    _logger.info("CLEANUP FINISHED")

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
