import odoo.tools
from odoo.tools import NON_BREAKING_SPACE, float_round, get_lang


# noinspection PyPep8Naming
def formatLang(env, value, digits=None, grouping=True, monetary=False, dp=False, currency_obj=False):
    """
    fix odoo's function to avoid negative zeros (-0.0)
    """

    if digits is None:
        digits = 2

        if dp:
            decimal_precision_obj = env['decimal.precision']
            digits = decimal_precision_obj.precision_get(dp)
        elif currency_obj:
            digits = currency_obj.decimal_places

    if isinstance(value, str) and not value:
        return ''

    lang_obj = get_lang(env)

    res = lang_obj.format(
        f'%.{digits}f', float_round(value, precision_digits=digits) + 0, grouping=grouping, monetary=monetary
    )

    if currency_obj and currency_obj.symbol:
        if currency_obj.position == 'after':
            res = f'{res}{NON_BREAKING_SPACE}{currency_obj.symbol}'

        elif currency_obj and currency_obj.position == 'before':
            res = f'{currency_obj.symbol}{NON_BREAKING_SPACE}{res}'
    return res


# monkey patching
odoo.tools.formatLang = formatLang
