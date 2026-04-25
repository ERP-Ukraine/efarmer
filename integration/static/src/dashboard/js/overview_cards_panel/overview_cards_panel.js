/** @odoo-module **/

import { DEMO_SALES_CARDS } from '../demo/data';
import { AbstractDashboardComponent } from '../abstract/abstract_dashboard_component';

import {
    AverageOrderValueCard, NumberOfOrdersCard, RepeatPurchaseRateCard, TotalSalesRevenueCard
} from './overview_cards';


export class SalesCardsPanel extends AbstractDashboardComponent {
    setup() {
        super.setup();

        this.getSelectedIntegrations = this.props.getSelectedIntegrations;
        this._triggerUpdate();
    }

    get cards() {
        return this.state.rawData || [];
    }

    async fetchData() {
        return await this.rpc('/integration-dashboard/get-sales-cards', {
            start_date: this.props.start,
            end_date: this.props.end,
            integration_ids: this.props.getSelectedIntegrations(),
            force_refresh: this.props.updateKey > 0,
        });
    }

    fetchDefaultData() {
        return Promise.resolve(DEMO_SALES_CARDS);
    }
}

SalesCardsPanel.components = {
    AverageOrderValueCard,
    NumberOfOrdersCard,
    RepeatPurchaseRateCard,
    TotalSalesRevenueCard,
};
SalesCardsPanel.props = [
    'start',
    'end',
    'updateKey',
    'blurGlobal',
    'selectedIntegrationId',
    'getSelectedIntegrations',
];
SalesCardsPanel.template = 'integration.SalesCardsPanelTemplate';
