# See LICENSE file for full copyright and licensing details.

import hashlib

from .base import GqlDict
from .translatable_resource import format_gid_key

from ..exceptions import ShopifyApiError


def get_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def format_translation_key(value: str, locale: str = None) -> str:
    return f'{format_gid_key(value, locale)}_translations'


def format_locale_key(value: str, locale: str = None) -> str:
    return f'{format_gid_key(value, locale)}_locales'


class Translation(GqlDict):

    _gid_name = 'Translation'
    _body = GqlDict._tmpl.TRANSLATION_BODY

    get_digest = staticmethod(get_digest)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._payload_push = []
        self._payload_remove = []

    def __repr__(self):
        return f'{self._gid_name}({self["locale"]}, {self["key"]}, outdated={self["outdated"]})'

    def __bool__(self):
        return bool(self['key'] and self['value'] and self['locale'])

    def to_dict(self):
        result = super().to_dict()

        result['_payload_push'] = self.payload_push
        result['_payload_remove'] = self.payload_remove

        return result

    def set(self, **kwargs: dict):
        if '_payload_push' in kwargs:
            self._payload_push = kwargs.pop('_payload_push')

        if '_payload_remove' in kwargs:
            self._payload_remove = kwargs.pop('_payload_remove')

        result = super().set(**kwargs)

        return result

    @property
    def payload_push(self):
        return self._payload_push

    @property
    def payload_remove(self):
        return self._payload_remove

    def clear_payload_push(self):
        self._payload_push = []

    def clear_payload_remove(self):
        self._payload_remove = []

    # --- PUSH ---
    def add_target_to_push(self, gid: str, key: str, value: str, primary_value: str, locale: str):
        translation = {
            'key': key,
            'value': value,
            'locale': locale,
            'translatableContentDigest': get_digest(primary_value),
        }
        self._payload_push.append([
            (format_gid_key(gid, locale), gid),
            (format_translation_key(gid, locale), translation),
        ])

    def prepare_variables_push(self):
        values = dict(set(x for [x, __] in self.payload_push))

        for translation_key, translation in (y for [__, y] in self.payload_push):
            if translation_key not in values:
                values[translation_key] = []

            values[translation_key].append(translation)

        return values

    def assemble_body_push(self):
        args, payload = [], ''

        for gid_key, translation_key in set((x[0], y[0]) for [x, y] in self.payload_push):
            args.append(f'${gid_key}: ID!, ${translation_key}: [TranslationInput!]!,')

            payload += """
                %s: translationsRegister(resourceId: $%s, translations: $%s) {
                    translations { %s }
                    userErrors { %s }
                }
            """ % (gid_key, gid_key, translation_key, self._tmpl.TRANSLATION_BODY, self._tmpl.USER_ERRORS_BODY_1)

        header = 'mutation translationsRegisterMultiple(%s)' % ' '.join(args)

        return '%s { %s }' % (header, payload)

    def push(self):
        if not self.payload_push:
            return []

        body = self.assemble_body_push()
        response = self._env.execute(body, variables=self.prepare_variables_push())

        errors = [x['userErrors'] for x in response['data'].values() if x['userErrors']]
        if errors:
            raise ShopifyApiError(str(errors))

        result = [self._new(**y) for x in response['data'].values() for y in x['translations']]

        self.clear_payload_push()

        return result

    # --- REMOVE ---
    def add_target_to_remove(self, gid: str, keys: list, locales: list):
        self._payload_remove.append([
            (format_gid_key(gid), gid),
            (format_translation_key(gid), keys),
            (format_locale_key(gid), locales),
        ])

    def prepare_variables_remove(self):
        return dict(sum(self.payload_remove, []))

    def assemble_body_remove(self):
        args, payload = [], ''

        for [(gid_key, __), (keys_key, __), (locales_key, __)] in self.payload_remove:
            args.append(f'${gid_key}: ID!, ${keys_key}: [String!]!, ${locales_key}: [String!]!,')

            payload += """
                %s: translationsRemove(resourceId: $%s, translationKeys: $%s, locales: $%s) {
                    translations { %s }
                    userErrors { %s }
                }
            """ % (gid_key, gid_key, keys_key, locales_key, self._tmpl.TRANSLATION_BODY, self._tmpl.USER_ERRORS_BODY_1)

        header = 'mutation translationsRemoveMulti(%s)' % ' '.join(args)

        return '%s { %s }' % (header, payload)

    def remove(self):
        if not self.payload_remove:
            return []

        body = self.assemble_body_remove()
        response = self._env.execute(body, variables=self.prepare_variables_remove())

        errors = [x['userErrors'] for x in response['data'].values() if x['userErrors']]
        if errors:
            raise ShopifyApiError(str(errors))

        result = [self._new(**y) for x in response['data'].values() for y in x['translations']]

        self.clear_payload_remove()

        return result
