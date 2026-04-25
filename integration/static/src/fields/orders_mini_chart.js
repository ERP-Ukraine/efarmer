/** @odoo-module **/

import { Component } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { loadJS } from '@web/core/assets';
import { useEffect, useRef, onWillDestroy, onWillStart } from '@odoo/owl';
import { standardFieldProps } from '@web/views/fields/standard_field_props';

export class OrdersMiniChart extends Component {
    static template = 'integration.OrdersMiniChartField';
    static props = { ...standardFieldProps };

    setup() {
        this.chart = null;
        this.canvasRef = useRef('canvas');

        onWillStart(async () => await loadJS('/web/static/lib/Chart/Chart.js'));

        onWillDestroy(() => {
            this.destroyChart();
        });

        useEffect(
            () => {
                this.renderChart();
            },
            () => [this.chartData],
        );
    }

    get chartData() {
        return this.props.record.data[this.props.name] || { labels: [], values: [] };
    }

    get hasData() {
        const data = this.chartData;
        return data.values && data.values.some(v => v > 0);
    }

    get totalOrders() {
        const data = this.chartData;
        if (!data.values) return 0;
        return data.values.reduce((sum, val) => sum + val, 0);
    }

    get suggestedMax() {
        const data = this.chartData;
        if (!data.values || data.values.length === 0) return 5;

        const maxValue = Math.max(...data.values);

        // Add 10% margin, with minimum of 2 for small values
        const margin = Math.max(maxValue * 0.1, 2);
        return Math.ceil(maxValue + margin);
    }

    destroyChart() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    renderChart() {
        this.destroyChart();

        const canvas = this.canvasRef.el;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const data = this.chartData;

        if (!this.hasData) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            return;
        }

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.values,
                    borderColor: 'rgba(40, 167, 69, 0.8)',
                    borderWidth: 2,
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: {
                        top: 10,
                        right: 5,
                        left: 5,
                    },
                },
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        enabled: true,
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: (context) => `${context.parsed.y} orders`,
                        },
                    },
                },
                scales: {
                    x: {
                        display: true,
                        grid: {
                            display: false,
                        },
                        ticks: {
                            font: {
                                size: 9,
                            },
                            maxRotation: 0,
                        },
                    },
                    y: {
                        display: false,
                        beginAtZero: true,
                        suggestedMax: this.suggestedMax,
                    },
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false,
                },
            },
        });
    }
}

export const ordersMiniChartField = {
    component: OrdersMiniChart,
    supportedTypes: ['json'],
};

registry.category('fields').add('orders_mini_chart', ordersMiniChartField);
