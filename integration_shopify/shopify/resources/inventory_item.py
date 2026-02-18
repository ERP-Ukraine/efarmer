# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceUpdate


class InventoryItem(ShopifyResourceUpdate):

    _gid_name = 'InventoryItem'
    _request_name = 'inventoryItem'
    _body = ShopifyResourceUpdate._tmpl.INVENTORY_ITEM_BODY

    MUTATION_INVENTORY_SET_QTY = ShopifyResourceUpdate._tmpl.MUTATION_INVENTORY_SET_QTY
    MUTATION_UPDATE = ShopifyResourceUpdate._tmpl.MUTATION_INVENTORY_ITEM_UPDATE
    MUTATION_ACTIVATE_INVENTORY_ITEM = ShopifyResourceUpdate._tmpl.MUTATION_ACTIVATE_INVENTORY_ITEM

    @property
    def variant(self):
        self.ensure_one()
        return self._env.ProductVariant.set(**(self['variant'] or {}))

    @property
    def weight(self):
        self.ensure_one()
        return self.measurement['weight']['value']

    @property
    def weight_unit(self):
        self.ensure_one()
        return self._env.WeightUnit.convert_weight_unit_in(self.measurement['weight']['unit'])

    @property
    def unit_cost(self):
        self.ensure_one()
        return self['unitCost']

    @property
    def cost(self):
        unit_cost = self.unit_cost

        if not unit_cost:
            return 0
        return float(self.unitCost['amount'])

    @property
    def currency(self):
        unit_cost = self.unit_cost

        if not unit_cost:
            return None
        return self.unitCost['currencyCode']

    @property
    def inventory_levels(self):
        self.ensure_one()
        return [self._env.InventoryLevel.set(**x) for x in (self['inventoryLevels'] or [])]

    @property
    def locations(self):
        self.ensure_one()
        return [x.location for x in self.inventory_levels]

    def update_item(self, **kwargs):
        """
        Available args:

            cost: float
            tracked: bool
            countryCodeOfOrigin: str
            provinceCodeOfOrigin: str
            harmonizedSystemCode: str
            countryHarmonizedSystemCodes: list of dicts
        """
        self.ensure_one()

        response = self.execute(
            self.MUTATION_UPDATE,
            variables={
                'id': self.gid,
                'input': kwargs,
            },
            user_errors_path='data.inventoryItemUpdate.userErrors',
        )

        values = self._extract(response, 'data.inventoryItemUpdate.inventoryItem', dict)
        self.set(**values)

        return self

    def update_quantity(self, location_id: str, quantity: int):
        self.ensure_one()
        return self.update_quantity_batch([(self.gid, location_id, quantity)])

    def update_quantity_batch(self, data: list):
        """
        :data: list of tuples
            [(item_id, location_id, quantity), ...]
        """

        payload = {
            'name': 'available',
            'reason': 'correction',
            'ignoreCompareQuantity': True,
            'quantities': [
                {
                    'inventoryItemId': self.create_gid(item_id),
                    'locationId': self._env.Location.create_gid(location_id),
                    'quantity': int(quantity),
                } for (item_id, location_id, quantity) in data
            ],
        }

        response = self.execute(
            self.MUTATION_INVENTORY_SET_QTY,
            variables={
                'input': payload,
            },
            user_errors_path='data.inventorySetQuantities.userErrors',
        )

        return self._extract(response, 'data.inventorySetQuantities.inventoryAdjustmentGroup.changes', list)

    def activate_inventory_item(self, inventory_item_id: str, location_id: str, quantity: int):
        """
        Activate an inventory item at a location.
        """
        response = self.execute(
            self.MUTATION_ACTIVATE_INVENTORY_ITEM,
            variables={
                'available': int(quantity),
                'locationId': self._env.Location.create_gid(location_id),
                'inventoryItemId': self.create_gid(inventory_item_id),
            },
            user_errors_path='data.inventoryActivate.userErrors',
        )

        result = self._extract(response, 'data.inventoryActivate.inventoryLevel', {})

        inventory_level = self._env.InventoryLevel.set(**result)
        item = inventory_level.item

        if not item.tracked:
            item.update_item(tracked=True)

        return inventory_level
