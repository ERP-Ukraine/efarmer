/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

export class PrintNodeScenarioBannerListRenderer extends ListRenderer {
    static template = "printnode_base.PrintNodeScenarioListView";
}

export const printNodeScenarioListView = {
    ...listView,
    Renderer: PrintNodeScenarioBannerListRenderer,
};

registry.category("views").add(
    "printnode_scenarios_list",
    printNodeScenarioListView
);
