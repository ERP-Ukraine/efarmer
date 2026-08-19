/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

export class PrintNodeWorkstationBannerListRenderer extends ListRenderer {
    static template = "printnode_base.PrintNodeWorkstationListView";
}

export const printNodeWorkstationListView = {
    ...listView,
    Renderer: PrintNodeWorkstationBannerListRenderer,
};

registry.category("views").add(
"printnode_workstations_list",
    printNodeWorkstationListView
);
