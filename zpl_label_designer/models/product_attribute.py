from odoo import api, models


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    @api.model
    def _get_lang_codes(self):
        """
        Get codes of installed languages, the current language first: attribute names
        are most likely written in it.
        """
        current_lang_code = self.env.lang or 'en_US'
        other_lang_codes = [
            lang_code for lang_code, _lang_name in self.env['res.lang'].get_installed()
            if lang_code != current_lang_code
        ]

        return [current_lang_code] + other_lang_codes

    def _find_by_name(self, name):
        """
        Find the attribute in self by its name in any installed language, the current one first.
        """
        for lang_code in self._get_lang_codes():
            attributes = self.with_context(lang=lang_code).filtered(
                lambda attribute: attribute.name == name
            )

            if attributes:
                return attributes[:1].with_env(self.env)

        return self.browse()

    @api.model
    def _search_by_names(self, names):
        """
        Search attributes by names in any installed language (the current language first).
        Returns a dict {name: attributes}.
        """
        attributes_by_name = {}
        names_to_search = list(names)

        for lang_code in self._get_lang_codes():
            if not names_to_search:
                break

            attributes = self.with_context(lang=lang_code).search_fetch(
                [('name', 'in', names_to_search)],
                ['name'],
            )

            for name, name_attributes in attributes.grouped('name').items():
                attributes_by_name[name] = name_attributes.with_env(self.env)

            names_to_search = [name for name in names_to_search if name not in attributes_by_name]

        return attributes_by_name
