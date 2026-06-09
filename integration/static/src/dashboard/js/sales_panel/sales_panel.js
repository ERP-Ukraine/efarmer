/** @odoo-module **/

import { DEMO_SALES_DATA } from '../demo/data';
import { AbstractDashboardComponent } from '../abstract/abstract_dashboard_component';
import { SalesOverTimeCard } from './sales_over_time';
import { SalesDistributionCard } from './sales_distribution';

export class SalesDataPanel extends AbstractDashboardComponent {
    setup() {
        super.setup();

        this.getSelectedIntegrations = this.props.getSelectedIntegrations;
        this._triggerUpdate();
    }

    get salesOverTime() {
        return this.state.rawData?.sales_over_time || { labels: [], values: [] };
    }

    get orderValueDistribution() {
        return this.state.rawData?.order_value_distribution || { labels: [], values: [] };
    }

    async fetchData() {
        return await this.rpc('/integration-dashboard/get-sales-data', {
            start_date: this.props.start,
            end_date: this.props.end,
            integration_ids: this.props.getSelectedIntegrations(),
            force_refresh: this.props.updateKey > 0,
        });
    }

    fetchDefaultData() {
        return Promise.resolve(DEMO_SALES_DATA);
    }
}

SalesDataPanel.props = [
    'start',
    'end',
    'updateKey',
    'blurGlobal',
    'selectedIntegrationId',
    'getSelectedIntegrations',
];
SalesDataPanel.template = 'integration.SalesDataTemplate';
SalesDataPanel.components = {
    SalesOverTimeCard,
    SalesDistributionCard,
}
