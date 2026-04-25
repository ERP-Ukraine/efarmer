/** @odoo-module **/

import { Component } from '@odoo/owl';

import { loadJS } from '@web/core/assets';
import { useEffect, useRef, onWillDestroy, onWillStart } from '@odoo/owl';

export class AbstractChartComponent extends Component {
    setup() {
        this.header = null;
        this.chart = null;

        this.canvasRef = useRef('canvas');
        this.data = this.props.data;

        onWillStart(async () => await loadJS('/web/static/lib/Chart/Chart.js'));

        onWillDestroy(() => {
            this.destroyChart();
        });

        useEffect(
            () => {
                this.data = this.props.data;  // TODO: wierd thing
                this.renderChart();
            },
            () => [this.props.data],
        );
    }

    get isValidData() {
        return this.data.labels.length > 0;
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
        const ctx = canvas.getContext('2d');

        if (this.isValidData) {
            this.chart = new Chart(ctx, this.getChartConfig());;
        } else {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    }

    getChartConfig() {
        throw new Error('getChartConfig() must be implemented by subclasses');
    }
}
