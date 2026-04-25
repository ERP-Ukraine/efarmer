# See LICENSE file for full copyright and licensing details.


class TranslationsMixin:

    _translatable = True

    def create_gid_key(self):
        self.ensure_one()
        return '_'.join(self.gid.split('/')[-2:])
