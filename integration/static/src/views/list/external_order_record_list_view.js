/** @odoo-module **/

import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { ListRenderer } from '@web/views/list/list_renderer';

// Shared list renderer for the four external order-record lists (fulfillments,
// payment transactions, returns, refunds). Injects a single header panel that
// explains what the records are and the row colour key. The same colour scheme
// and legend are used on every one of these lists, so one renderer serves all.
export class ExternalOrderRecordListRenderer extends ListRenderer {
    static template = 'integration.ExternalOrderRecordListView';
}

registry.category('views').add('external_order_record_list_view', {
    ...listView,
    Renderer: ExternalOrderRecordListRenderer,
});
