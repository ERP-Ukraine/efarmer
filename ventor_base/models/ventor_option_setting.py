# Copyright 2022 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, models, fields


class VentorOptionSetting(models.Model):
    _name = 'ventor.option.setting'
    _description = 'Ventor Option Setting'

    name = fields.Char(required=True, index=True)
    action_type = fields.Selection(
        [
            ('warehouse_opration', 'Warehouse Opration'),
            ('package_management', 'Package Management'),
            ('batch_picking', 'Batch Picking'),
            ('wave_picking', 'Wave Picking'),
            ('cluster_picking', 'Cluster Picking'),
            ('internal_transfers', 'Internal Transfers'),
            ('putaway', 'Putaway'),
            ('instant_inventory', 'Instant Inventory'),
            ('inventory_adjustments', 'Inventory Adjustments'),
            ('quick_info', 'Quick Info'),
            ('scrap_management', 'Scrap Management'),
            ('create_so', 'Create SO'),
            ('create_po', 'Create PO'),
        ], required=True
    )
    description = fields.Text()
    technical_name = fields.Char(required=True)
    value = fields.Many2one(
        'ventor.setting.value',
        string='Value',
        required=True,
        domain="[('id', 'in', settings_dependency)]",
    )
    value_type = fields.Selection(
        [
            ('bool', 'Boolean'),
            ('select', 'Selection'),
        ]
    )
    settings_dependency = fields.Many2many(
        comodel_name='ventor.setting.value'
    )

    @api.onchange('value')
    def _onchange_value(self):
        if self.technical_name in ('confirm_source_location', 'change_source_location'):
            return self._set_change_source_location()
        elif self.technical_name in ('add_boxes_before_cluster', 'multiple_boxes_for_one_transfer'):
            return self._set_add_boxes_before_cluster()
        elif self.technical_name in (
            'manage_packages',
            'confirm_source_package',
            'scan_destination_package',
            'allow_creating_new_packages',
            'pack_all_items',
            'allow_validate_less',
        ):
            return self.set_related_package_fields(self._get_group_settings_value('stock.group_tracking_lot'))
        elif self.technical_name in ('manage_product_owner'):
            self.set_manage_product_owner_fields(self._get_group_settings_value('stock.group_tracking_owner'))
        elif self.technical_name in ('apply_default_lots'):
            self.set_apply_default_lots_fields(self._get_group_settings_value('stock.group_production_lot'))
        elif self.technical_name in ('move_multiple_products', 'hold_destination_location'):
            return self.set_hold_destination_location_fields()
        elif self.technical_name in ('use_reusable_packages'):
            return self.set_reusable_packages_related_fields(self._get_group_settings_value('stock.group_tracking_lot'))
        elif self.technical_name in ('confirm_destination_location'):
            self._set_confirm_destination_location_cluster_picking_fields()

    def _get_group_settings_value(self, key):
        internal_user_groups = self.env.ref('base.group_user').implied_ids
        group = self.env.ref(key)
        return group in internal_user_groups

    def _get_warning(self, message):
        return {'warning': {
                'title': _('Another Settings were changed automatically!'),
                'message': message,
            }}

    def get_setting_field(self, technical_name):
        if not isinstance(technical_name, list):
            technical_name = [technical_name]
        return self.env['ventor.option.setting'].search(
            [
                ('action_type', '=', self.action_type),
                ('technical_name', 'in', technical_name),
            ]
        )

    def get_general_settings(self):
        action_types = [
            'package_management',
            'batch_picking',
            'wave_picking',
            'cluster_picking',
            'internal_transfers',
            'putaway',
            'instant_inventory',
            'inventory_adjustments',
            'quick_info',
            'scrap_management',
            'create_so',
            'create_po',
        ]
        ventor_option_settings = self.env['ventor.option.setting'].search([])

        settings = {}
        for action_type in action_types:
            settings[action_type] = {
                set.technical_name: self.get_normalized_value(set.value.setting_value)
                for set in ventor_option_settings.filtered(lambda r: r.action_type == action_type)
            }
        return settings

    def set_allow_validate_less(self):
        if self.technical_name == 'allow_validate_less':
            pack_all_items = self.get_setting_field('pack_all_items')
            if pack_all_items.value == self.env.ref('ventor_base.bool_true'):
                self.value = self.env.ref('ventor_base.bool_false')
        elif self.technical_name == 'pack_all_items':
            allow_validate_less = self.get_setting_field('allow_validate_less')
            if allow_validate_less.value == self.env.ref('ventor_base.bool_true'):
                allow_validate_less.value = self.env.ref('ventor_base.bool_false')
                return self._get_warning(_(
                    'Because you changed "Force Pack" to True, '
                    'automatically the following settings were also changed: '
                    '\n- "Validate uncompleted orders" was changed to False'
                ))

    def set_apply_default_lots_fields(self, group_stock_production_lot):
        if self.env.context.get('disable_apply_default_lots'):
            self.value = self.env.ref('ventor_base.bool_false')
        elif not group_stock_production_lot and self.value == self.env.ref('ventor_base.bool_true'):
            self.value = self.env.ref('ventor_base.bool_false')

    def _set_add_boxes_before_cluster(self):
        if self.technical_name == 'add_boxes_before_cluster' and self.value == self.env.ref('ventor_base.bool_true'):
            multiple_boxes_for_one_transfer = self.get_setting_field('multiple_boxes_for_one_transfer')
            use_reusable_packages = self.get_setting_field('use_reusable_packages')
            if multiple_boxes_for_one_transfer.value == self.env.ref('ventor_base.bool_true'):
                multiple_boxes_for_one_transfer.value = self.env.ref('ventor_base.bool_false')
                return self._get_warning(_(
                    'Because you changed "Add boxes before cluster" to True, '
                    'automatically the following settings were also changed: '
                    '\n- "Multiple boxes for one transfer" was changed to False'
                ))
            if use_reusable_packages.value == self.env.ref('ventor_base.bool_true'):
                self.value = self.env.ref('ventor_base.bool_false')
        elif self.technical_name == 'multiple_boxes_for_one_transfer' and self.value == self.env.ref('ventor_base.bool_true'):
            add_boxes_before_cluster = self.get_setting_field('add_boxes_before_cluster')
            if add_boxes_before_cluster.value == self.env.ref('ventor_base.bool_true'):
                self.value = self.env.ref('ventor_base.bool_false')

    def _set_change_source_location(self):
        if self.technical_name == 'confirm_source_location' and self.value == self.env.ref('ventor_base.bool_false'):
            change_source_location = self.get_setting_field('change_source_location')
            change_source_location.value = self.env.ref('ventor_base.bool_false')
            return self._get_warning(_(
                'Because you changed "​Confirm source location" to False, '
                'automatically the following settings were also changed: '
                '\n- "Change source location" was changed to False'
            ))
        elif self.technical_name == 'change_source_location' and self.value == self.env.ref('ventor_base.bool_true'):
            confirm_source_location = self.get_setting_field('confirm_source_location')
            if confirm_source_location.value == self.env.ref('ventor_base.bool_false'):
                self.value = self.env.ref('ventor_base.bool_false')

    def _set_confirm_destination_location_cluster_picking_fields(self):
        if self.value == self.env.ref('ventor_base.bool_true') and self.action_type == 'cluster_picking':
            use_reusable_packages = self.get_setting_field('use_reusable_packages')
            if use_reusable_packages.value == self.env.ref('ventor_base.bool_true'):
                self.value = self.env.ref('ventor_base.bool_false')

    def set_hold_destination_location_fields(self):
        if self.technical_name == 'move_multiple_products' and self.value == self.env.ref('ventor_base.bool_true'):
            hold_destination_location = self.get_setting_field('hold_destination_location')
            if hold_destination_location.value == self.env.ref('ventor_base.bool_true'):
                hold_destination_location.value = self.env.ref('ventor_base.bool_false')
                return self._get_warning(_(
                    'Because you changed "Move multiple items" to True, '
                    'automatically the following settings were also changed: '
                    '\n- "Hold destination location" was changed to False'
                ))
        elif self.technical_name == 'hold_destination_location' and self.value == self.env.ref('ventor_base.bool_true'):
            move_multiple_products = self.get_setting_field('move_multiple_products')
            if move_multiple_products.value == self.env.ref('ventor_base.bool_true'):
                self.value = self.env.ref('ventor_base.bool_false')

    def set_manage_product_owner_fields(self, group_stock_tracking_owner):
        if not group_stock_tracking_owner and self.value == self.env.ref('ventor_base.bool_true'):
            self.value = self.env.ref('ventor_base.bool_false')

    def set_related_package_fields(self, group_stock_tracking_lot):
        if not group_stock_tracking_lot:
            self.value = self.env.ref('ventor_base.bool_false')
        elif group_stock_tracking_lot:
            manage_packages = self.get_setting_field('manage_packages')
            if self.value.setting_value == 'False' and self.technical_name == 'manage_packages':
                relate_manage_packages_fields = self.get_setting_field(
                    [
                        'confirm_source_package',
                        'scan_destination_package',
                    ]
                )
                relate_manage_packages_fields.value = self.env.ref('ventor_base.bool_false')
                if self.action_type in ('batch_picking', 'cluster_picking'):
                    return self._get_warning(_(
                        'Because you changed "Show packages fields" to False, '
                        'automatically the following settings were also changed: '
                        '\n- "Confirm source package" was changed to False'
                        '\n- "Confirm destination package" was changed to False'
                    ))
            if self.technical_name != 'manage_packages' and manage_packages.value == self.env.ref('ventor_base.bool_false'):
                self.value = self.env.ref('ventor_base.bool_false')
            if self.value.setting_value == 'True' and self.technical_name in ('pack_all_items', 'allow_validate_less'):
                return self.set_allow_validate_less()
            if self.technical_name == 'scan_destination_package' and self.value == self.env.ref('ventor_base.bool_false'):
                use_reusable_packages = self.get_setting_field('use_reusable_packages')
                if use_reusable_packages.value == self.env.ref('ventor_base.bool_true'):
                    self.value = self.env.ref('ventor_base.bool_true')

    def set_reusable_packages_related_fields(self, group_stock_tracking_lot):
        if not group_stock_tracking_lot:
            self.value = self.env.ref('ventor_base.bool_false')
        elif self.value == self.env.ref('ventor_base.bool_true'):
            related_settings_for_disabling = self.get_setting_field(
                [
                    'confirm_destination_location',
                    'add_boxes_before_cluster',
                ]
            )
            related_settings_for_enabling = self.get_setting_field('scan_destination_package')
            if related_settings_for_disabling:
                related_settings_for_disabling.value = self.env.ref('ventor_base.bool_false')
            if related_settings_for_enabling:
                related_settings_for_enabling.value = self.env.ref('ventor_base.bool_true')
            return self._get_warning(_(
                'Because you changed "Use reusable packages" to True, '
                'automatically the following settings were also changed: '
                '\n- "Confirm destination location" was changed to False'
                '\n- "Add boxes before cluster" was changed to False'
                '\n- "Confirm destination package" was changed to True'
            ))

    def get_normalized_value(self, setting_value):
        normalized_settings = {
            'True': 'true',
            'False': 'false',
            'Always Create Backorder': 'always_create_backorder',
            'Never Create Backorder': 'never_create_backorder',
            'Always Split the Line': 'always_split_line',
            'Always Move Less Items': 'always_move_less_items',
            'Ask Me Every Time': 'ask_me_every_time',
        }
        return normalized_settings.get(setting_value)


class VentorSettingValue(models.Model):
    _name = 'ventor.setting.value'
    _description = 'Ventor Setting Value'
    _rec_name = 'setting_value'

    setting_type = fields.Char()
    setting_value = fields.Char()
