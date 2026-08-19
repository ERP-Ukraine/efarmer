/** @odoo-module **/

import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { ListRenderer } from '@web/views/list/list_renderer';

export class PrintNodePrintRuleBannerListRenderer extends ListRenderer {
    static template = 'printnode_base.PrintNodePrintRuleListView';
}

registry.category('views').add('printnode_print_rules_list', {
    ...listView,
    Renderer: PrintNodePrintRuleBannerListRenderer,
});
