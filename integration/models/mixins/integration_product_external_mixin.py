# See LICENSE file for full copyright and licensing details.

from typing import List

from odoo import models, _
from odoo.exceptions import UserError, ValidationError

from ...tools import ExternalImage


HIGH_MATCH_LEVEL = 'high'
MIDDLE_MATCH_LEVEL = 'middle'
LOW_MATCH_LEVEL = 'low'
MINIMAL_MATCH_LEVEL = 'minimal'


class IntegrationProductExternalMixin(models.AbstractModel):
    _name = 'integration.product.external.mixin'
    _description = 'Integration Product External Mixin'
    _odoo_model = None

    @property
    def is_template(self):
        return self._odoo_model == 'product.template'

    @property
    def template_code(self):
        if self.is_template:
            return self.code
        return self.code.split('-')[0]

    @property
    def variant_code(self):
        if self.is_template:
            return False
        return self.code.split('-')[1]

    @property
    def all_image_external_ids(self):
        return self.env['integration.product.image.external'].search([
            ('integration_id', '=', self.integration_id.id),
            ('template_code', '=', self.template_code),
        ])

    @property
    def all_image_mapping_ids(self):
        return self.all_image_external_ids.mapping_ids

    @property
    def image_mapping_ids(self):
        mappings = self.all_image_mapping_ids

        if self.is_template:
            mappings = mappings.filtered(lambda x: not x.variant_code)
        else:
            mappings = mappings.filtered(lambda x: x.variant_code == self.variant_code)

        return mappings

    @property
    def image_mappings_lack_or_in_none_state(self):
        mappings = self.all_image_mapping_ids
        if not mappings:
            return True
        return all(mappings.mapped(lambda x: x.to_none))

    def _prepare_images_mappings_to_export(self) -> List[ExternalImage]:
        result = [self._init_image_dataclass_out()]

        for image in self.odoo_record._get_extra_images():
            datacls = self._init_image_dataclass_out(image_id=image.id)
            result.append(datacls)

        return [x for x in result if x]

    def _init_image_dataclass_out(self, image_id=None):
        product = self.odoo_record

        if not product:
            raise ValidationError(
                _('Missed Odoo mapping for the external record: %s') % self.format_recordset()
            )

        if image_id:
            checksum = self.env['product.image'].browse(image_id).image_checksum
        else:
            checksum = product.image_checksum

        if not checksum:
            return False  # Product with empty image_1920 field

        # 1. HIGH_MATCH_LEVEL: existing mapping without any changes. The `variant_code` field is essential --> used the
        # `image_mapping_ids` property instead of `all_image_mapping_ids`. No needs to do anything, mark it as `none`.
        mapping = self._find_suitable_mapping_out(checksum, image_id=image_id, match_level=HIGH_MATCH_LEVEL)

        if mapping:
            mapping.mark_none()
            return ExternalImage.from_mapping(mapping)

        # 2. MIDDLE_MATCH_LEVEL: used most likely when cover image was selected from existing and mapped extra images
        # (`variant_code` field is still essential). In that case, we need to update the [image_id, is_cover] fields
        # and mark it as `assign`.
        mapping = self._find_suitable_mapping_out(checksum, image_id=image_id, match_level=MIDDLE_MATCH_LEVEL)

        if mapping:
            mapping.write({
                'image_id': image_id,
                'is_cover': not image_id,
            })
            mapping.mark_assign()
            return ExternalImage.from_mapping(mapping)

        values = {
            'ttype': product._name,
            'res_id': product.id,
            'image_id': image_id,
            'is_cover': not image_id,
            'variant_code': self.variant_code,
        }

        # 3. LOW_MATCH_LEVEL: the same as MIDDLE_MATCH_LEVEL but searching in all mappings
        # (`all_image_mapping_ids` --> `variant_code` is not essential). It mean the image was reassigned from one
        # variant to another. Update it with valid values and mark as `assign`.
        mapping = self._find_suitable_mapping_out(checksum, image_id=image_id, match_level=LOW_MATCH_LEVEL)

        if mapping:
            mapping.write(values)
            mapping.mark_assign()
            return ExternalImage.from_mapping(mapping)

        # 4. MINIMAL_MATCH_LEVEL: mapping found by checksum amount all existing mappings
        # (not only in the `in_pending` status). Highly likely it is the mapping previously founded in
        # HIGH, MIDDLE, LOW levels so make a copy, update with actual values and mark as `assign`.
        # In most cases it means that one variant has the same image as another variant.
        mapping = self._find_suitable_mapping_out(checksum, image_id=image_id, match_level=MINIMAL_MATCH_LEVEL)

        if mapping:
            mapping_ = mapping.copy(default={**values, 'external_image_id': mapping.external_image_id.id})
            mapping_.mark_assign()
            mapping = mapping_
        else:
            # If mapping wasn't found, create a new one.
            external = self._init_empty_external_image()
            mapping = external._create_image_mapping(**values, checksum=checksum)
            mapping.mark_create()

        return ExternalImage.from_mapping(mapping)

    def _find_suitable_mapping_out(self, checksum: str, image_id: int = None, match_level: str = HIGH_MATCH_LEVEL):
        """Redefined for the integration_magento2 module"""
        if match_level == HIGH_MATCH_LEVEL:
            mappings = self.image_mapping_ids.filtered(lambda x: x.in_pending and x.checksum == checksum)
            if image_id:
                mappings = mappings.filtered(lambda x: x.image_id.id == image_id)
            else:
                mappings = mappings.filtered(lambda x: x.is_cover)
        elif match_level == MIDDLE_MATCH_LEVEL:
            mappings = self.image_mapping_ids.filtered(lambda x: x.in_pending and x.checksum == checksum)
        elif match_level == LOW_MATCH_LEVEL:
            mappings = self.all_image_mapping_ids.filtered(lambda x: x.in_pending and x.checksum == checksum)
        elif match_level == MINIMAL_MATCH_LEVEL:
            mappings = self.all_image_mapping_ids.filtered(lambda x: x.checksum == checksum)
        else:
            raise UserError(_('Unknown match level: %s') % match_level)

        return mappings[:1]

    def _update_image_mappings_in(self, datacls_list: List[ExternalImage]):
        product = self.odoo_record

        values = {
            'ttype': product._name,
            'res_id': product.id,
            'variant_code': self.variant_code,
        }
        mappings = self.env['integration.product.image.mapping']

        for datacls in datacls_list:
            values['is_cover'] = datacls.is_cover

            externals = self.all_image_external_ids
            external = externals.filtered(lambda x: x.code == datacls.code)

            if not external:
                external = externals.create(datacls._to_external_dict())
                mapping = external._create_image_mapping(**values)
            else:
                mapping = external._create_or_update_image_mapping_in(**values)

            mapping.mark_none()
            mappings |= mapping

        return mappings

    def _init_empty_external_image(self):
        return self.env['integration.product.image.external'].create({
            'src': False,  # Update it after export finished
            'code': False,  # Update it after export finished
            'template_code': self.template_code,
            'integration_id': self.integration_id.id,
        })

    def _create_internal_import_line(self):
        return self.env['import.product.line'].create({
            'origin_id': self.id,
            'name': self.name,
            'code': self.code,
            'reference': self.external_reference,
            'barcode': self.external_barcode,
            'mapping_id': self.mapping_record.id,
            'odoo_id': self.odoo_record.id,
            'model_name': self._odoo_model,
            'type': 'internal',
        })
