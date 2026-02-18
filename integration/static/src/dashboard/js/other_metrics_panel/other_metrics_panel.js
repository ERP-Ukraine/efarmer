/** @odoo-module **/

import { DEMO_STORE_PERFORMANCE } from '../demo/data';
import { AbstractDashboardComponent } from '../abstract/abstract_dashboard_component';
import { CountriesBreakdownCard } from './countries_breakdown';
import { CustomersBreakdownCard } from './customers_breakdown';
import { StorePerformanceBreakdownCard } from './store_performance_breakdown';

// FIXME: Split this component to multiple? Bad naming
export class OtherMetricsPanel extends AbstractDashboardComponent {
    setup() {
        super.setup();
        this._triggerUpdate();
    }

    get stores() {
        return this.state.rawData?.stores || [];
    }

    get countries() {
        return this.state.rawData?.countries || [];
    }

    get customers() {
        return this.state.rawData?.customers || { labels: [], values: [] };
    }

    async fetchData() {
        return await this.rpc('/integration-dashboard/get-store-performance', {
            start_date: this.props.start,
            end_date: this.props.end,
            integration_ids: this.props.getSelectedIntegrations(),
            force_refresh: this.props.updateKey > 0,
        });
    }

    fetchDefaultData() {
        return Promise.resolve(DEMO_STORE_PERFORMANCE);
    }
}

OtherMetricsPanel.props = [
    'start',
    'end',
    'updateKey',
    'blurGlobal',
    'selectedIntegrationId',
    'getSelectedIntegrations',
];
OtherMetricsPanel.template = 'integration.OtherMetricsPanelTemplate';
OtherMetricsPanel.components = {
    StorePerformanceBreakdownCard,
    CustomersBreakdownCard,
    CountriesBreakdownCard,
}
