/** @odoo-module **/

import { AbstractCard } from './abstract_card';


export class TotalSalesRevenueCard extends AbstractCard {
    get value() {
        return `${this.currency} ${this.props.data.value.toLocaleString()}`;
    }
}

export class NumberOfOrdersCard extends AbstractCard {
    get value() {
        return this.props.data.value;
    }
}

export class AverageOrderValueCard extends AbstractCard {
    get value() {
        if (this.props.data.value) {
            const averageValue = `${this.currency} ${this.props.data.value.average.toLocaleString()}`;
            const medianValue = `${this.currency} ${this.props.data.value.median.toLocaleString()}`;
            return `${averageValue} / ${medianValue}`;
        }
        return `${this.currency} 0 / ${this.currency} 0`;
    }
}

export class RepeatPurchaseRateCard extends AbstractCard {
    get value() {
        return `${this.props.data.value}%`;
    }
}
