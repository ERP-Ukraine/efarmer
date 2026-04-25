/** @odoo-module **/

import { AbstractChartComponent } from '../abstract/abstract_chart_component';

export class CustomersBreakdownCard extends AbstractChartComponent {

    setup() {
        super.setup();
        this.header = 'New vs Returning Customers';
    }

    getChartConfig() {
        return {
            type: 'bar',
            data: {
                labels: this.props.data.labels,
                datasets: [{
                    label: 'New vs Returning Customers (%)',
                    data: this.props.data.values,
                    backgroundColor: [
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
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        min: 0,
                        max: 100,
                        ticks: {
                            callback: function (value) {
                                return value + '%';
                            },
                        },
                    },
                    y: {
                        type: 'category',
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const dataset = context.dataset;
                                const currentValue = dataset.data[context.dataIndex];
                                return currentValue + '%';
                            },
                        },
                    },
                    legend: {
                        display: false,
                    },
                },
            },
        };
    }
}

CustomersBreakdownCard.props = ['data'];
CustomersBreakdownCard.template = 'integration.GenericChartCardTemplate';
