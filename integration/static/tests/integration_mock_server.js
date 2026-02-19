/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { MockServer } from "@web/../tests/helpers/mock_server";

patch(MockServer.prototype, {
    /**
     * Simulate the `systray_get_integrations` route response to render StatusMenu
     * @override
     */
    async _performRPC(route, args) {
        if (args.model === 'sale.integration' && args.method === 'systray_get_integrations') {
            return Promise.resolve([]);
        }
        return super._performRPC(...arguments);
    },
});
