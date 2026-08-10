/** @odoo-module **/

import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { ListRenderer } from '@web/views/list/list_renderer';

export class SaleIntegrationInputFileListRenderer extends ListRenderer {
    static template = 'integration.SaleIntegrationInputFileListView';
}

registry.category('views').add('sale_integration_input_file_list_view', {
    ...listView,
    Renderer: SaleIntegrationInputFileListRenderer,
});
