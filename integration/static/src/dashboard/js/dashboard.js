/** @odoo-module **/

import { rpc } from '@web/core/network/rpc';
import { registry } from '@web/core/registry';
import { Component, useState, onWillStart } from '@odoo/owl';

import { IntegrationDashboardFilter } from './dashboard_filter';
import { SalesCardsPanel } from './overview_cards_panel/overview_cards_panel';
import { SalesDataPanel } from './sales_panel/sales_panel';
import { ProductsPanel } from './products_panel/products_panel';
import { OtherMetricsPanel } from './other_metrics_panel/other_metrics_panel';

export class IntegrationDashboard extends Component {
    setup() {

        this.state = useState({
            start: this.getDateMonthsAgo(1),
            end: this.formatDate(new Date()),
            integrations: [],
            selectedIntegrationId: 0,
            updateKey: 0,
            blurGlobal: false,
        });

        onWillStart(async () => {
            await this.loadIntegrations();
            this.state.blurGlobal = this.state.integrations.length === 0;
        });
    }

    updateSelectedIntegrations(id) {
        this.state.selectedIntegrationId = id;
    }

    updateComponents() {
        this.state.updateKey += 1;
    }

    updateDates(start, end) {
        this.state.start = start;
        this.state.end = end;
    };

    async loadIntegrations() {
        const integrations = await rpc('/integration-dashboard/get-active-integrations', {});
        this.state.integrations = integrations;
    }

    formatDate(date) {
        return date.toISOString().split('T')[0];
    }

    getDateMonthsAgo(months) {
        const date = new Date();
        date.setMonth(date.getMonth() - months);
        return this.formatDate(date);
    }

    getSelectedIntegrations() {
        if (this.state.selectedIntegrationId === 0) {
            return this.state.integrations.map(integration => integration.id);
        } else {
            return [this.state.selectedIntegrationId];
        }
    }
}

IntegrationDashboard.template = 'integration.IntegrationDashboardTemplate';
IntegrationDashboard.components = {
    IntegrationDashboardFilter,
    SalesCardsPanel,
    SalesDataPanel,
    ProductsPanel,
    OtherMetricsPanel,
};

registry.category('actions').add('integration_dashboard.client_action', IntegrationDashboard);
