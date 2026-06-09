/** @odoo-module **/

import { Component } from '@odoo/owl';


export class AbstractCard extends Component {
    get currency() {
        return this.props.data.currency_symbol || '$';
    }

    get title() {
        return this.props.data.title;
    }

    get value() {
        return this.props.data.value;
    }

    get percent() {
        return this.props.data.percent;
    }
};

AbstractCard.props = ['data'];
AbstractCard.template = 'integration.AbstractCard';
