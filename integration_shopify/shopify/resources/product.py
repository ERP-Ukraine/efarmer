# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceUpdate
from .product_mixin import ProductMixin


class Product(ShopifyResourceUpdate, ProductMixin):

    _gid_name = 'Product'
    _request_name = 'product'
    _body = ShopifyResourceUpdate._tmpl.PRODUCT_BODY

    PRODUCT_GET_ATTRIBUTES_BODY = ShopifyResourceUpdate._tmpl.PRODUCT_GET_ATTRIBUTES_BODY

    MUTATION_CREATE = ShopifyResourceUpdate._tmpl.MUTATION_CREATE_PRODUCT_ASYNCHRONOUS
    MUTATION_UPDATE = ShopifyResourceUpdate._tmpl.MUTATION_PRODUCT_UPDATE
    MUTATION_DELETE = ShopifyResourceUpdate._tmpl.MUTATION_PRODUCT_DELETE

    MUTATION_PRODUCT_REORDER_MEDIA = ShopifyResourceUpdate._tmpl.MUTATION_PRODUCT_REORDER_MEDIA
    MUTATION_PRODUCT_VARIANT_APPEND_MEDIA = ShopifyResourceUpdate._tmpl.MUTATION_PRODUCT_VARIANT_APPEND_MEDIA
    MUTATION_PRODUCT_VARIANT_DETACH_MEDIA = ShopifyResourceUpdate._tmpl.MUTATION_PRODUCT_VARIANT_DETACH_MEDIA

    MUTATION_CREATE_PRODUCT_OPTIONS = ShopifyResourceUpdate._tmpl.MUTATION_CREATE_PRODUCT_OPTIONS
    MUTATION_UPDATE_PRODUCT_OPTIONS = ShopifyResourceUpdate._tmpl.MUTATION_UPDATE_PRODUCT_OPTIONS
    MUTATION_DELETE_PRODUCT_OPTIONS = ShopifyResourceUpdate._tmpl.MUTATION_DELETE_PRODUCT_OPTIONS

    MUTATION_BULK_CREATE_PRODUCT_VARIANTS = ShopifyResourceUpdate._tmpl.MUTATION_BULK_CREATE_PRODUCT_VARIANTS
    MUTATION_BULK_UPDATE_PRODUCT_VARIANTS = ShopifyResourceUpdate._tmpl.MUTATION_BULK_UPDATE_PRODUCT_VARIANTS
    MUTATION_BULK_DELETE_PRODUCT_VARIANTS = ShopifyResourceUpdate._tmpl.MUTATION_BULK_DELETE_PRODUCT_VARIANTS

    @property
    def external_id(self):
        return self.id_str

    @property
    def status(self):
        return self._env.ProductStatus(self['status'])

    @property
    def is_active(self):
        return self.status.is_active

    @property
    def is_archived(self):
        return self.status.is_archived

    @property
    def is_draft(self):
        return self.status.is_draft

    @property
    def has_only_default_variant(self):
        # The template with options which are not used for variants creation.
        # This is a special case for Shopify, when the product has only one variant and no options.
        return self['hasOnlyDefaultVariant']

    @property
    def has_only_one_variant(self):
        # Template with only one variant no matter if it has options or not.
        return len(self.variants) == 1

    @property
    def is_gift_card(self):
        return self['isGiftCard']

    @property
    def featured_media_gid(self):
        self.ensure_one()
        return self.featuredMedia and self['featuredMedia']['id']

    @property
    def variants(self):
        if not self.key_exist('variants'):
            self.read()
            self.raise_if_no_key('variants')

        return [self._env.ProductVariant.set(**vals) for vals in (self['variants'] or [])]

    @property
    def collections(self):
        if not self.key_exist('collections'):
            self.read()
            self.raise_if_no_key('collections')

        return [self._env.Collection.set(**vals) for vals in (self['collections'] or [])]

    @property
    def options(self):
        self.ensure_one()
        return [self._env.ProductOption.set(**vals) for vals in (self['options'] or [])]

    @property
    def formatted_options(self):
        if not self.key_exist('options'):
            self.read()
            self.raise_if_no_key('options')

        result = []
        for option in self.options:
            # If the attribute name is default and there is only one default value - skip it
            if (
                option.name == self.ATTRIBUTE_DEFAULT_TITLE
                and len(option.option_values) == 1
                and option.option_values[0].name == self.ATTRIBUTE_DEFAULT_VALUE
            ):
                continue

            for value in option.option_values:
                result.append((option.name, value.name))

        return result

    @property
    def tags(self):
        if not self.key_exist('tags'):
            self.read()
            self.raise_if_no_key('tags')

        return self['tags'] or []

    def to_dict(self, simple_identifier: bool = False):
        result = super().to_dict()

        if not result:
            return result

        if simple_identifier:
            result['id'] = self.id_str

        return result

    def image_exists_on_variants(self, image_id: str) -> bool:
        self.ensure_one()

        image_gid = self._env.MediaImage.create_gid(image_id)
        variants_media = sum([x.media for x in self.variants], [])

        return any(x.gid == image_gid for x in variants_media)

    def get_attributes(self):
        self.ensure_one()
        attributes = set(x[0] for x in self.formatted_options)
        return [{'id': self.format_attr_code(x), 'name': x} for x in attributes]

    def get_attribute_values(self):
        self.ensure_one()
        return [
            {
                'id': self.format_attr_value_code(option, value),
                'id_group': self.format_attr_code(option),
                'id_group_name': option,
                'name': value,
            } for (option, value) in self.formatted_options
        ]

    def read_metafields_recursively(self):
        self.ensure_one()

        _body = self._prepare_metafields_body()
        body = '%s variants(first: 250) { nodes { %s } }' % (_body, _body)

        self.read(body=body)

        return self.to_dict()

    def create_product_all_in_one(self, params: dict):
        """
        Create a product with all its variants and options in one request.
        """
        self.ensure_new()

        response = self.execute(
            self.MUTATION_CREATE,
            variables={'productSet': params},
            user_errors_path='data.productSet.userErrors',
        )
        gid = self._extract(response, 'data.productSet.product.id', str)

        self.set(id=gid)
        self.read()

        return self

    def update(self, values: dict):
        self.ensure_one()

        values_ = self._prepare_update_values(values)

        response = self.execute(
            self.MUTATION_UPDATE,
            variables={
                'product': {
                    'id': self.gid,
                    **values_,
                },
            },
            user_errors_path='data.productUpdate.userErrors',
        )

        return self._extract(response, 'data.productUpdate.product', dict)

    def bulk_create_variants(self, variants_data: list):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_BULK_CREATE_PRODUCT_VARIANTS,
            variables={
                'productId': self.gid,
                'variants': variants_data,
            },
            user_errors_path='data.productVariantsBulkCreate.userErrors',
        )

        result = self._extract(response, 'data.productVariantsBulkCreate.productVariants', list)
        return [self._env.ProductVariant.set(**x) for x in result]

    def bulk_update_variants(self, variants_data: list):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_BULK_UPDATE_PRODUCT_VARIANTS,
            variables={
                'productId': self.gid,
                'variants': variants_data,
            },
            user_errors_path='data.productVariantsBulkUpdate.userErrors',
        )

        return self._extract(response, 'data.productVariantsBulkUpdate.productVariants', list)

    def bulk_delete_variants(self, variant_ids: list = None):
        self.ensure_one()

        if variant_ids:
            ids = [self._env.ProductVariant.create_gid(str(x)) for x in variant_ids]
        else:
            ids = [x.gid for x in self.variants]

        response = self.execute(
            self.MUTATION_BULK_DELETE_PRODUCT_VARIANTS,
            variables={
                'productId': self.gid,
                'variantsIds': ids,
            },
            user_errors_path='data.productVariantsBulkDelete.userErrors',
        )

        return self._extract(response, 'data.productVariantsBulkDelete', dict)

    def delete_product_media(self):
        self.ensure_one()

        media_ids = self.media_image_gids
        return self._env.MediaImage.delete_batch(media_ids)

    def append_images_to_variants(self, variant_media: list):
        self.ensure_one()

        # 1. Deatch old media from variant
        self.detach_images_from_variants([x['variantId'] for x in variant_media])

        # 2. Append new media to variants
        response = self.execute(
            self.MUTATION_PRODUCT_VARIANT_APPEND_MEDIA,
            variables={
                'productId': self.gid,
                'variantMedia': variant_media,
            },
            user_errors_path='data.productVariantAppendMedia.userErrors',
        )

        return self._extract(response, 'data.productVariantAppendMedia', dict)

    def detach_images_from_variants(self, variant_ids: list):
        self.ensure_one()

        variant_media = []
        variant_gids = [self._env.ProductVariant.create_gid(str(x)) for x in variant_ids]

        for variant in self.variants:
            if variant.gid in variant_gids and variant.media:
                variant_media.append({
                    'mediaIds': [x.gid for x in variant.media],
                    'variantId': variant.gid,
                })

        if not variant_media:
            return {}

        response = self.execute(
            self.MUTATION_PRODUCT_VARIANT_DETACH_MEDIA,
            variables={
                'productId': self.gid,
                'variantMedia': variant_media,
            },
            user_errors_path='data.productVariantDetachMedia.userErrors',
        )

        return self._extract(response, 'data.productVariantDetachMedia', dict)

    def set_image_as_cover(self, image_id: str):
        self.ensure_one()

        image_gid = self._env.MediaImage.create_gid(image_id)

        response = self.execute(
            self.MUTATION_PRODUCT_REORDER_MEDIA,
            variables={
                'id': self.gid,
                'moves': [
                    {
                        'id': image_gid,
                        'newPosition': '0',
                    },
                ],
            },
            user_errors_path='data.productReorderMedia.mediaUserErrors',
        )

        self.set(featuredMedia={'id': image_gid})

        return self._extract(response, 'data.productReorderMedia.job.id', str)

    def _prepare_update_values(self, values: dict):
        self.ensure_one()

        # 1. Handle collections
        if 'collections' in values:
            values['collectionsToJoin'] = values.pop('collections')

        if 'collectionsToJoin' in values:
            collection_gids = [self._env.Collection.create_gid(x) for x in values['collectionsToJoin']]
            existing_collection_gids = [x.gid for x in self.collections]
            values['collectionsToJoin'] = collection_gids

            collections_to_leave = set(existing_collection_gids).difference(set(collection_gids))
            if collections_to_leave:
                values['collectionsToLeave'] = list(collections_to_leave)
            elif set(collection_gids) == set(existing_collection_gids):
                del values['collectionsToJoin']

        return values

    def _update_options(self, attribute_values: list):
        """
        :attribute_values:
            [
                {
                    "name": "color",
                    "values": [
                        {
                            "name": "Gold"
                        },
                        {
                            "name": "Blue"
                        }
                    ]
                },
                {
                    "name": "size",
                    "values": [
                        {
                            "name": "M"
                        },
                        {
                            "name": "L"
                        },
                        {
                            "name": "XL"
                        }
                    ]
                }
            ]
        """
        self.ensure_one()

        if self.has_only_default_variant:
            action1 = action2 = False
        else:
            action1 = self._run_options_delete_if_needed(attribute_values)
            action2 = self._run_option_values_delete_if_needed(attribute_values)

        action3 = self._run_options_create_if_needed(attribute_values)

        if any((action1, action2, action3)):
            self.read()

        return self.options

    def _run_options_create_if_needed(self, attribute_values: list):
        self.ensure_one()

        payload = []
        names = [x.name for x in self.options]

        for attribute in attribute_values:
            if attribute['name'] not in names:
                payload.append(attribute)

        if payload:
            response = self.execute(
                self.MUTATION_CREATE_PRODUCT_OPTIONS,
                variables={
                    'productId': self.gid,
                    'options': payload,
                    # Existing variants are updated with the first option value of each added option  New variants
                    # are created for each combination of existing variant option values and new option values.
                    'variantStrategy': 'CREATE',
                },
                user_errors_path='data.productOptionsCreate.userErrors',
            )

            options = self._extract(response, 'data.productOptionsCreate.product.options', list)
            self['options'] = options
            return True

        return False

    def _run_option_values_delete_if_needed(self, attribute_values: list):
        """Currently we are only deleting unnecessary option values"""
        self.ensure_one()

        refresh = False
        attributes_by_name = {x['name']: x['values'] for x in attribute_values}

        for option in self.options:
            option_values_to_add, option_values_delete_ids = [], []

            option_name = option.name
            if option_name in attributes_by_name:
                input_option_values = [x['name'] for x in attributes_by_name[option_name]]

                # 1. Delete unnecessary option values
                for option_value in option.option_values:
                    if option_value.name not in input_option_values:
                        option_values_delete_ids.append(option_value.gid)

            # 3. Update option
            if option_values_delete_ids or option_values_to_add:
                self.execute(
                    self.MUTATION_UPDATE_PRODUCT_OPTIONS,
                    variables={
                        'productId': self.gid,
                        'option': {
                            'id': option.gid,
                        },
                        'optionValuesToDelete': option_values_delete_ids,
                        # Variants are created and deleted according to the option values to add and to delete.
                        'variantStrategy': 'MANAGE',
                    },
                    user_errors_path='data.productOptionUpdate.userErrors',
                )
                refresh = True

        if refresh:
            self.read()
            return True

        return False

    def _run_options_delete_if_needed(self, attribute_values: list):
        self.ensure_one()
        names_by_name = {x.name: x.gid for x in self.options}

        for attribute in attribute_values:
            name = attribute['name']
            if name in names_by_name:
                del names_by_name[name]

        if names_by_name:
            response = self.execute(
                self.MUTATION_DELETE_PRODUCT_OPTIONS,
                variables={
                    'productId': self.gid,
                    'options': list(names_by_name.values()),
                    # An Option with multiple values can be deleted. Remaining variants will be deleted,
                    # highest position first, in the event of duplicates being detected.
                    'strategy': 'POSITION',
                },
                user_errors_path='data.productOptionsDelete.userErrors',
            )
            options = self._extract(response, 'data.productOptionsDelete.product.options', list)
            self['options'] = options
            return True

        return False

    def _serialize_for_validation_test(self, *, sku, barcode):
        self.ensure_one()

        kwargs = dict(sku=sku, barcode=barcode)
        variants = [x._serialize_variant_for_test(**kwargs) for x in self.variants]

        return [self._serialize_template_for_test()] + variants

    def _serialize_template_for_test(self):
        return {
            'id': self.id_str,
            'name': self.title,
            'barcode': '',
            'ref': '',
            'parent_id': '',
            'skip_ref': True,
            'joint_namespace': False,
        }

    def _serialize_to_mappings(self, data: dict) -> list:
        """
        :data: Dict from fields converter (odoo: convert_to_external)
        """
        mappings = [{
            'model': 'product.template',
            'id': data['id'],
            'odoo_external_id': data['odoo_external_id'],
            'external_id': self.id_str,
            'attribites_data': {
                'formatted_options': self.get_attributes(),
                'formatted_option_values': self.get_attribute_values(),
            },
        }]

        for variant in self.variants:
            for variant_data in data['products']:
                if getattr(variant, variant_data['reference_api_field']) == variant_data['reference']:
                    mappings.append({
                        'model': 'product.product',
                        'id': variant_data['id'],
                        'odoo_external_id': variant_data['odoo_external_id'],
                        'external_id': variant.external_id,
                    })

        return mappings

    def _get_option_id_by_name(self, option_name: str):
        for option in self.options:
            if option.name == option_name:
                return option.gid

        return None

    def _find_suitable_variant_by_options(self, options: list):
        for variant in self.variants:
            variant_options = [(x.name, x.value) for x in variant.selected_options]
            if set(variant_options) == set(options):
                return variant

        return None
