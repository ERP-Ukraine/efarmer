import typing
from unittest.mock import patch

import odoo.tools.misc
from odoo.api import Environment
from odoo.tools.float_utils import float_round as orig_float_round


def local_float_round(value, precision_digits=None, precision_rounding=None, rounding_method='HALF-UP'):
    return (
        orig_float_round(
            value=value,
            precision_digits=precision_digits,
            precision_rounding=precision_rounding,
            rounding_method=rounding_method,
        )
        + 0
    )


# noinspection PyPep8Naming
def formatLang(
    env: Environment,
    value: float | typing.Literal[''],
    digits: int = 2,
    grouping: bool = True,
    monetary: bool | odoo.tools.misc.Sentinel = odoo.tools.misc.SENTINEL,
    dp: str | None = None,
    currency_obj=None,
    rounding_method: typing.Literal['HALF-UP', 'HALF-DOWN', 'HALF-EVEN', 'UP', 'DOWN'] = 'HALF-EVEN',
    rounding_unit: typing.Literal['decimals', 'units', 'thousands', 'lakhs', 'millions'] = 'decimals',
) -> str:
    with patch('odoo.tools.float_utils.float_round', local_float_round):
        return originalFormatLang(
            env=env,
            value=value,
            digits=digits,
            grouping=grouping,
            monetary=monetary,
            dp=dp,
            currency_obj=currency_obj,
            rounding_method=rounding_method,
            rounding_unit=rounding_unit,
        )


# monkey patching
originalFormatLang = odoo.tools.misc.formatLang

odoo.tools.misc.formatLang = formatLang
# odoo.tools.formatLang = formatLang
