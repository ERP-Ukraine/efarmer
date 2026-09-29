# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceUpdate


class InventoryItem(ShopifyResourceUpdate):

    _gid_name = 'InventoryItem'
    _request_name = 'inventoryItem'
    _body = ShopifyResourceUpdate._tmpl.INVENTORY_ITEM_BODY

    MUTATION_INVENTORY_SET_QTY = ShopifyResourceUpdate._tmpl.MUTATION_INVENTORY_SET_QTY
    MUTATION_UPDATE = ShopifyResourceUpdate._tmpl.MUTATION_INVENTORY_ITEM_UPDATE
    MUTATION_ACTIVATE_INVENTORY_ITEM = ShopifyResourceUpdate._tmpl.MUTATION_ACTIVATE_INVENTORY_ITEM

    def get_variants(self):
        """Every variant backed by this inventory item.

        Usually one, but combined listings/bundles can share a single
        inventory item across several variants, so the deprecated singular
        `variant` field is no longer a reliable 1:1 lookup. Populated only
        when the query body included INVENTORY_ITEM_VARIANTS_BODY (the
        inventory-level/stock-sync path) -- empty otherwise.

        The embedded page is capped at INVENTORY_ITEM_VARIANTS_PAGE_SIZE to
        keep the batch query that fetches many inventory levels at once
        cheap. A full page is the only sign there may be more, since that
        batch query has no room for per-item cursors -- when it happens,
        page through a dedicated query against this one item instead.

        That signal is unreliable once resolved: a fully-fetched item can
        itself legitimately hold exactly PAGE_SIZE variants, which would
        keep looking "possibly truncated" forever. A context flag marks
        the fetch as done so a repeated call reuses the cached result
        instead of re-issuing it.
        """
        self.ensure_one()

        if not self.ctx('variants_fetched', bool):
            nodes = self['variants'] or []

            if len(nodes) == self._tmpl.INVENTORY_ITEM_VARIANTS_PAGE_SIZE:
                nodes = self._fetch_all_variant_nodes()

            self.set(variants=nodes)
            self.add_context(variants_fetched=True)

        return [self._env.ProductVariant.set(**node) for node in (self['variants'] or [])]

    def _fetch_all_variant_nodes(self):
        query = '''
            query($id: ID!, $cursor: String) {
                inventoryItem(id: $id) {
                    variants(first: 250, after: $cursor) {
                        nodes {
                            id
                            product {
                                id
                            }
                        }
                        pageInfo {
                            endCursor
                            hasNextPage
                        }
                    }
                }
            }
        '''
        nodes = []
        cursor = None

        while True:
            response = self.execute(query, variables={'id': self.gid, 'cursor': cursor})
            data = self._extract(response, 'data.inventoryItem.variants', dict) or {}
            nodes.extend(data.get('nodes') or [])

            page_info = data.get('pageInfo') or {}
            if not page_info.get('hasNextPage'):
                break
            cursor = page_info.get('endCursor')

        return nodes

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
        return self._update_quantity_batch([(self.gid, location_id, quantity)])

    def update_quantity_batch(self, data: list):
        """
        :data: list of tuples
            [(item_id, location_id, quantity), ...]
        """

        result = []
        for i in range(0, len(data), 250):
            response = self._update_quantity_batch(data[i:i + 250])
            result.append(response)

        return result

    def _update_quantity_batch(self, data: list):
        payload = {
            'name': 'available',
            'reason': 'correction',
            'quantities': [
                {
                    'quantity': int(quantity),
                    'changeFromQuantity': None,
                    'inventoryItemId': self.create_gid(item_id),
                    'locationId': self._env.Location.create_gid(location_id),
                } for (item_id, location_id, quantity) in data
            ],
        }

        idempotency_key = self.generate_idempotency_key()

        response = self.execute(
            self.MUTATION_INVENTORY_SET_QTY % idempotency_key,
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
        variables = {
            'available': int(quantity),
            'locationId': self._env.Location.create_gid(location_id),
            'inventoryItemId': self.create_gid(inventory_item_id),
        }

        idempotency_key = self.generate_idempotency_key()

        response = self.execute(
            self.MUTATION_ACTIVATE_INVENTORY_ITEM % idempotency_key,
            variables=variables,
            user_errors_path='data.inventoryActivate.userErrors',
        )

        result = self._extract(response, 'data.inventoryActivate.inventoryLevel', {})

        inventory_level = self._env.InventoryLevel.set(**result)
        item = inventory_level.item

        if not item.tracked:
            item.update_item(tracked=True)

        return inventory_level
