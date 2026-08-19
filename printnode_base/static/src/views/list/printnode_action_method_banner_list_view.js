/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

export class PrintNodeActionMethodBannerListRenderer extends ListRenderer {
    static template = "printnode_base.PrintNodeActionMethodListView";
}

export const printNodeActionMethodListView = {
    ...listView,
    Renderer: PrintNodeActionMethodBannerListRenderer,
};

registry.category("views").add(
    "printnode_action_methods_list",
    printNodeActionMethodListView
);
