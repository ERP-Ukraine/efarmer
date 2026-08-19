/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

export class PrintNodePrintJobBannerListRenderer extends ListRenderer {
    static template = "printnode_base.PrintNodePrintJobListView";
}

export const printNodePrintJobListView = {
    ...listView,
    Renderer: PrintNodePrintJobBannerListRenderer,
};

registry.category("views").add(
    "printnode_printjobs_list",
    printNodePrintJobListView
);
