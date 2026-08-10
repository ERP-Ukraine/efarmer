# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class Duty(GqlDict):

    _gid_name = 'Duty'
    _body = GqlDict._tmpl.DUTY_BODY

    @property
    def price_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['price'] or {}))

    @property
    def tax_lines(self):
        self.ensure_one()
        return [self._env.TaxLine.set(**x) for x in (self['taxLines'] or [])]
