/** @odoo-module **/

import { AbstractChartComponent } from '../abstract/abstract_chart_component';

export class SalesOverTimeCard extends AbstractChartComponent {

    setup() {
        super.setup();
        this.header = 'Sales Over Time';
    }

    getChartConfig() {
        const symbolPart = this.data.currency_symbol
            ? ', ' + this.data.currency_symbol
            : '';

        return {
            type: 'line',
            data: {
                labels: this.data.labels,
                datasets: [{
                    label: 'Sales per Month' + symbolPart,
                    data: this.data.values,
                    borderColor: 'rgba(0, 150, 136, 0.7)',
                    borderWidth: 2,
                    backgroundColor: 'rgba(0, 150, 136, 0.2)',
                    tension: 0.1,
                    fill: true,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'category',
                        reverse: false,
                    },
                    y: {
                        beginAtZero: true,
                    },
                },
            },
        };
    }
}

SalesOverTimeCard.props = ['data'];
SalesOverTimeCard.template = 'integration.GenericChartCardTemplate';
