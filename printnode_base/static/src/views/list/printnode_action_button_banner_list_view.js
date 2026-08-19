/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

export class PrintNodeActionButtonBannerListRenderer extends ListRenderer {
    static template = "printnode_base.PrintNodeActionButtonListView";
}

export const printNodeActionButtonListView = {
    ...listView,
    Renderer: PrintNodeActionButtonBannerListRenderer,
};

registry.category("views").add(
    "printnode_action_buttons_list",
    printNodeActionButtonListView
);
