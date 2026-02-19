# See LICENSE file for full copyright and licensing details.


class MetafieldMixin:

    @property
    def metafields(self):
        self.ensure_one()
        return [self._env.Metafield.set(**x) for x in (self['metafields'] or [])]

    def get_metafields(self):
        self.ensure_one()
        body = self._prepare_metafields_body()

        response = self.read(body=body)
        self.set(metafields=response['metafields'])

        return self.metafields

    def _prepare_metafields_body(self):
        return 'id metafields(first: 50) { nodes { %s } }' % self._tmpl.METAFIELD_BODY
