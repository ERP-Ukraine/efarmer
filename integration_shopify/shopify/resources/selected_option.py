# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class SelectedOption(GqlDict):

    _gid_name = 'SelectedOption'
    _body = GqlDict._tmpl.SELECTED_OPTION_BODY

    @property
    def id(self):
        return self.option_value.id

    @property
    def option_value(self):
        self.ensure_one()
        return self._env.ProductOptionValue.set(**(self['optionValue'] or {}))
