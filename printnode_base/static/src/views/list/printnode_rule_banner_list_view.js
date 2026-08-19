/** @odoo-module **/

import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { ListRenderer } from '@web/views/list/list_renderer';

export class PrintNodeRuleBannerListRenderer extends ListRenderer {
    static template = 'printnode_base.PrintNodeRuleListView';
}

registry.category('views').add('printnode_rules_list', {
    ...listView,
    Renderer: PrintNodeRuleBannerListRenderer,
});
