# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class CurrencySetting(GqlDict):

    _gid_name = 'CurrencySetting'
    _body = GqlDict._tmpl.CURRENCY_SETTING_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def currency_code(self):
        self.ensure_one()
        return self['currencyCode']

    @property
    def currency_name(self):
        self.ensure_one()
        return self['currencyName']
