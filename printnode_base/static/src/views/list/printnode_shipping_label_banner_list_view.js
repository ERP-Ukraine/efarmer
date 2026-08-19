/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

export class PrintNodeShippingLabelBannerListRenderer extends ListRenderer {
    static template = "printnode_base.PrintNodeShippingLabelListView";
}

export const printNodeShippingLabelListView = {
    ...listView,
    Renderer: PrintNodeShippingLabelBannerListRenderer,
};

registry.category("views").add(
    "printnode_shipping_labels_list",
    printNodeShippingLabelListView
);
