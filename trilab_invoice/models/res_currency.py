import logging

from odoo import models
from odoo.tools import get_iso_codes, get_lang

_logger = logging.getLogger(__name__)


class Currency(models.Model):
    _inherit = 'res.currency'

    def amount_to_text(self, amount):
        if not self.env.company.x_use_ti:
            return super().amount_to_text(amount)

        self.ensure_one()

        amount = '{:.2f}'.format(amount)

        # If template preview
        if preview_lang := self.env.context.get('template_preview_lang'):
            lang = get_iso_codes(preview_lang)

        else:
            lang = get_lang(self.env).iso_code

        try:
            # noinspection PyPackageRequirements
            from num2words import num2words

            # noinspection PyBroadException
            try:
                return num2words(amount, lang=lang, to='currency', currency=self.name)

            except NotImplementedError:
                _logger.warning(f'num2words - unsupported language {lang}/{self.name}')
                return ''

            except Exception:
                # currency convert unsupported for this language (no proper exception returned)
                return num2words(amount, lang=lang)

        except ImportError:
            _logger.warning('num2words not installed, no text2word for invoice')
            return ''

        except Exception as e:
            _logger.error('num2words - %s', e)
            return ''

    def round(self, amount):
        return super().round(amount) + 0.0
