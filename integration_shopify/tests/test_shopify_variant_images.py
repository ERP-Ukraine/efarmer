# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.addons.integration.tools import ActionType, ExternalImage, ProductType

from .init_integration_shopify import IntegrationShopifyBase
from .patch.resources_patch.product import Product
from ..shopify.resources.media_image import MediaImage


TEMPLATE_CODE = '10203545100500'
VARIANT_CODE = '51158197731620'
VARIANT_GID = 'gid://shopify/ProductVariant/%s' % VARIANT_CODE
VARIANT_COVER_GID = 'gid://shopify/MediaImage/1001'
VARIANT_EXTRA_GID = 'gid://shopify/MediaImage/1002'
TEMPLATE_COVER_GID = 'gid://shopify/MediaImage/1003'


@tagged('post_install', '-at_install')
class TestShopifyVariantImages(IntegrationShopifyBase):
    """A Shopify variant holds one image: only the main variant image is linked to it on export."""

    def setUp(self):
        super().setUp()
        self.appended = []

        def _append_images_to_variants(product_self, variant_media):
            self.appended.extend(variant_media)
            return []

        self.patch(Product, 'read', lambda product_self, *args, **kw: {})
        self.patch(Product, 'append_images_to_variants', _append_images_to_variants)
        self.patch(MediaImage, 'delete_batch', lambda media_self, file_ids: [])

    def _image(self, code, ttype, is_cover, action_type, variant_code=None):
        return ExternalImage(
            integration_id=self.integration.id,
            code=code,
            name=code.rsplit('/', 1)[-1],
            src=False,
            is_cover=is_cover,
            template_code=TEMPLATE_CODE,
            ttype=ttype,
            variant_code=variant_code,
            action_type=action_type,
        )

    def test_extra_variant_image_is_not_linked_to_variant(self):
        datacls_list = [
            self._image(TEMPLATE_COVER_GID, ProductType.PRODUCT_TEMPLATE, True, ActionType.NONE),
            self._image(
                VARIANT_COVER_GID, ProductType.PRODUCT_PRODUCT, True, ActionType.ASSIGN, variant_code=VARIANT_CODE,
            ),
            self._image(
                VARIANT_EXTRA_GID, ProductType.PRODUCT_PRODUCT, False, ActionType.ASSIGN, variant_code=VARIANT_CODE,
            ),
        ]

        self.adapter.export_template_images(TEMPLATE_CODE, datacls_list)

        self.assertEqual(self.appended, [{'mediaIds': [VARIANT_COVER_GID], 'variantId': VARIANT_GID}])

    def test_reassigned_extra_variant_image_keeps_variant_image(self):
        # An extra image shared with another variant is reassigned without touching the main image of this one
        datacls_list = [
            self._image(
                VARIANT_COVER_GID, ProductType.PRODUCT_PRODUCT, True, ActionType.NONE, variant_code=VARIANT_CODE,
            ),
            self._image(
                VARIANT_EXTRA_GID, ProductType.PRODUCT_PRODUCT, False, ActionType.ASSIGN, variant_code=VARIANT_CODE,
            ),
        ]

        self.adapter.export_template_images(TEMPLATE_CODE, datacls_list)

        self.assertEqual(self.appended, [])
