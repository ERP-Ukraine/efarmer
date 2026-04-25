/** @odoo-module **/

import { Component, useState } from '@odoo/owl';

export class IntegrationDashboardFilter extends Component {
    setup() {

        this.state = useState({
            start: this.props.start,
            end: this.props.end,
            blurGlobal: this.props.blurGlobal,
            selectedIntegrationId: this.props.selectedIntegrationId,
        });

        this.updateDates = this.props.updateDates;
        this.updateComponents = this.props.updateComponents;
    }

    onIntegrationChange(event) {
        const selectedValue = event.target.value;

        let integrationId;

        if (selectedValue === 'all') {
            integrationId = 0;
        } else {
            integrationId = parseInt(selectedValue, 10);
        }

        this.state.selectedIntegrationId = integrationId;
        this.props.updateSelectedIntegrations(integrationId);
    }

    onRefresh() {
        this.updateDates(this.state.start, this.state.end);
        this.updateComponents();
    }
}

IntegrationDashboardFilter.props = [
    'start',
    'end',
    'integrations',
    'selectedIntegrationId',
    'updateSelectedIntegrations',
    'blurGlobal',
    'updateDates',
    'updateComponents',
];
IntegrationDashboardFilter.template = 'integration.IntegrationDashboardFilterTemplate';
