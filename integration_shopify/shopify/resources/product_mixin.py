# See LICENSE file for full copyright and licensing details.

from .base import DeleteMixin
from .metafields_mixin import MetafieldMixin
from .translations_mixin import TranslationsMixin


class ProductMixin(MetafieldMixin, TranslationsMixin, DeleteMixin):

    ATTRIBUTE_DEFAULT_TITLE = 'Title'  # Default product attribute name according to the Shopify API
    ATTRIBUTE_DEFAULT_VALUE = 'Default Title'  # Default product attribute value according to the Shopify API
    SHOPIFY_ATTRIBUTE_PREFIX = 'shopify-attribute-'
    SHOPIFY_ATTRIBUTE_VALUE_PREFIX = 'shopify-attribute-value-'

    @property
    def media(self):
        self.ensure_one()

        if not self.key_exist('media'):
            self.get_media()

        media = [self._env.MediaImage.set(**vals) for vals in (self['media'] or [])]
        return list(filter(lambda x: x.is_image, media))

    @property
    def media_image_gids(self):
        self.ensure_one()
        return [x.gid for x in self.media]

    @staticmethod
    def format_attr_code(name):
        return f'{ProductMixin.SHOPIFY_ATTRIBUTE_PREFIX}{name}'

    @staticmethod
    def format_attr_value_code(option_name, option_value):
        return f'{ProductMixin.SHOPIFY_ATTRIBUTE_VALUE_PREFIX}{option_name}-{option_value}'

    def get_media(self):
        self.ensure_one()

        body = 'id media(first: 250) { nodes { %s } }' % self._env.Media.default_body()
        result = self.read(body=body, return_raw=True)

        self.set(media=result['media'])

        return self['media']
