from odoo import SUPERUSER_ID, api

from . import models

PARAMETER = 'trilab_jpk_base.taxoffice_loaded'


# noinspection PyUnusedLocal
def post_init_handler(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if not env['ir.config_parameter'].get_param(PARAMETER, False):
        env['jpk.taxoffice'].load_from_xml()
        env['ir.config_parameter'].set_param(PARAMETER, 'true')

    # hide main menu icon
    menu_data = env['ir.model.data'].search(
        [['name', '=', 'jpk_main_menu'], ['module', '=', 'trilab_jpk_base'], ['model', '=', 'ir.ui.menu']]
    )
    if menu_data:
        menu_item = env['ir.ui.menu'].browse([menu_data.res_id])
        menu_item.write({'active': False})


# noinspection PyUnusedLocal
def uninstall_handler(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # noinspection PyTypeChecker
    env['ir.config_parameter'].set_param(PARAMETER, None)
