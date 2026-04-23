from . import controllers, models, wizard

PARAMETER = 'trilab_jpk_base.taxoffice_loaded'


# noinspection PyUnusedLocal
def post_init_handler(env):
    if not env['ir.config_parameter'].get_param(PARAMETER):
        env['jpk.taxoffice'].load_from_xml()
        env['ir.config_parameter'].set_param(PARAMETER, 'true')

    # hide main menu icon
    try:
        env.ref('trilab_jpk_base.jpk_main_menu').write({'active': False})
    except ValueError:
        pass


# noinspection PyUnusedLocal
def uninstall_handler(env):
    # noinspection PyTypeChecker
    env['ir.config_parameter'].set_param(PARAMETER, None)
