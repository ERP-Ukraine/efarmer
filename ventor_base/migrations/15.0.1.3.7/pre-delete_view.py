def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        DELETE FROM ir_ui_view WHERE id in (select res_id from ir_model_data where name = 'res_user_form' and module='ventor_base');
    """)
