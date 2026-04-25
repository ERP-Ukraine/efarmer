/** @odoo-module **/

import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { ListRenderer } from '@web/views/list/list_renderer';

export class ProductEcommerceFieldListRenderer extends ListRenderer {
    static template = 'integration.ProductEcommerceFieldListView';
}

registry.category('views').add('product_ecommerce_field_list_view', {
    ...listView,
    Renderer: ProductEcommerceFieldListRenderer,
});
