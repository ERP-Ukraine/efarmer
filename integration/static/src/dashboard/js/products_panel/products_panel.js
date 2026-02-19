/** @odoo-module **/

import { DEMO_PRODUCTS } from '../demo/data';
import { AbstractDashboardComponent } from '../abstract/abstract_dashboard_component';

export class ProductsPanel extends AbstractDashboardComponent {
    setup() {
        super.setup();
        this._triggerUpdate();
    }

    get products() {
        return this.state.rawData?.products || [];
    }

    async fetchData() {
        return await this.rpc('/integration-dashboard/get-top-products', {
            start_date: this.props.start,
            end_date: this.props.end,
            integration_ids: this.props.getSelectedIntegrations(),
            force_refresh: this.props.updateKey > 0,
        });
    }

    async fetchDefaultData() {
        return Promise.resolve(DEMO_PRODUCTS);
    }
}

ProductsPanel.props = [
    'start',
    'end',
    'updateKey',
    'blurGlobal',
    'selectedIntegrationId',
    'getSelectedIntegrations',
];
ProductsPanel.template = 'integration.ProductsPanelTemplate';
