# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


def format_gid_key(value: str, locale: str = None) -> str:
    return '_'.join(value.split('/')[-2:]) + (f'_{locale}' if locale else '')


def parse_locale_from_gid_key(value: str) -> str:
    return value.split('_')[-1]


class TranslatableResource(GqlDict):

    _gid_name = 'TranslatableResource'
    _body = GqlDict._tmpl.TRANSLATABLE_RESOURCE_SAMPLE_BODY_1

    TRANSLATABLE_RESOURCE_CONTENT = GqlDict._tmpl.TRANSLATABLE_RESOURCE_SAMPLE_BODY_2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._locale = None
        self._payload_pull = set()
        self._metafields_data = {}

    def __repr__(self):
        if self.resource_id:
            name = '/'.join(self.resource_id.split('/')[-2:])
        else:
            name = '../..'

        return f'{self._gid_name}({name}, locale={self._locale})'

    def __bool__(self):
        return bool(self.resource_id)

    @property
    def payload_pull(self):
        return '\n'.join([(self.default_body() % x) for x in self._payload_pull])

    @property
    def resource_id(self):
        return self['resourceId']

    @property
    def translatable_content(self):
        return [self._env.TranslatableContent.set(**(x or {})) for x in (self['translatableContent'] or [])]

    @property
    def translations(self):
        return [self._env.Translation.set(**x) for x in (self['translations'] or [])]

    @property
    def nested_translatable_resources(self):
        return [self._new(**x) for x in (self['nestedTranslatableResources'] or [])]

    @property
    def has_nested_metafields(self):
        return any(('/Metafield/' in x.resource_id) for x in self.nested_translatable_resources)

    @property
    def metafields_data(self):
        return self._metafields_data

    def set_locale(self, locale: str):
        self._locale = locale

    def add_metafield_data(self, metafields_data: dict):
        self._metafields_data.update(metafields_data)

    def clear_payload_pull(self):
        self._payload_pull = set()

    def add_target_to_pull(self, gid: str, locale: str):
        self._payload_pull.add(
            (format_gid_key(gid, locale), gid, locale, locale)
        )

    def assemble_body_pull(self):
        return 'query { %s }' % self.payload_pull

    def pull(self):
        if not self.payload_pull:
            return []

        body = self.assemble_body_pull()
        response = self._env.execute(body)

        result = []

        for key, value in response['data'].items():
            if not value:
                continue

            record = self._new(**value)
            record.set_locale(parse_locale_from_gid_key(key))

            result.append(record)

        self.clear_payload_pull()

        return result

    def parse_translations(self) -> dict:
        result = {}

        # 0. Default translations
        for translatable_content in self.translatable_content:
            result[translatable_content.key] = {translatable_content.locale: translatable_content.value}

        # 1. Main translations
        for translation in self.translations:
            result[translation.key] = {translation.locale: translation.value}

        # 2. Nested resources translations
        if self.metafields_data:
            for resource in self.nested_translatable_resources:
                if resource.resource_id in self.metafields_data:
                    metafield = self._env.Metafield.set(**self.metafields_data[resource.resource_id])

                    for translation in resource.translations:
                        result[metafield.odoo_key] = {translation.locale: translation.value}

        return result

    def fetch_translatable_content(self, gid: str):
        body_ = self.TRANSLATABLE_RESOURCE_CONTENT % gid
        response = self._env.execute('query { %s }' % body_)

        self.set(**response['data']['translatableResource'])
        locale = self._parse_locale_from_body()
        self.set_locale(locale)

    def get_metafield_by_key(self, key: str):
        metafields = [self._env.Metafield.set(**x) for x in self.metafields_data.values()]

        for metafield in metafields:
            if metafield.odoo_key == key:
                return metafield

        return self._env.Metafield

    def get_primary_value_by_key(self, key: str):
        for rec in self.translatable_content:
            if rec.key == key:
                return rec.value

        return None

    def _parse_locale_from_body(self):
        content = self.translatable_content

        if not content:
            return None

        return content[0].locale
