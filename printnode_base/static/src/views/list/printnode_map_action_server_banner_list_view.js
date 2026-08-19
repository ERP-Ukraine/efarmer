/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

export class PrintNodeMapActionServerBannerListRenderer extends ListRenderer {
    static template = "printnode_base.PrintNodeMapActionServerListView";
}

export const printNodeMapActionServerListView = {
    ...listView,
    Renderer: PrintNodeMapActionServerBannerListRenderer,
};

registry.category("views").add(
    "printnode_map_action_servers_list",
    printNodeMapActionServerListView
);
