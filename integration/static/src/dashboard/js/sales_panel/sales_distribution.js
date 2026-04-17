/** @odoo-module **/

import { AbstractChartComponent } from '../abstract/abstract_chart_component';

export class SalesDistributionCard extends AbstractChartComponent {

    setup() {
        super.setup();
        this.header = 'Order Value Distribution';
    }

    getChartConfig() {
        return {
            type: 'pie',
            data: {
                labels: this.data.labels,
                datasets: [{
                    data: this.data.values,
                    backgroundColor: [
                        'rgba(255, 111, 0, 0.6)',
                        'rgba(0, 150, 136, 0.6)',
                        'rgba(103, 58, 183, 0.6)',
                    ],
                    borderColor: [
                        'rgba(245, 245, 245, 0.6)',
                    ],
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const dataset = context.dataset;
                                const dataIndex = context.dataIndex;
                                const currentValue = dataset.data[dataIndex];
                                const label = context.chart.data.labels[dataIndex];
                                return `${label}: ${currentValue}`;
                            },
                        },
                    },
                },
            },
        };
    }
}

SalesDistributionCard.props = ['data'];
SalesDistributionCard.template = 'integration.GenericChartCardTemplate';
