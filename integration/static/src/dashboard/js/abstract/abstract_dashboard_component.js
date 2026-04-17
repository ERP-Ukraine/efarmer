/** @odoo-module **/

import { rpc } from '@web/core/network/rpc';
import { Component, useEffect, useState } from '@odoo/owl';

export class AbstractDashboardComponent extends Component {
    setup() {
        this.state = useState({
            rawData: {},
            isLoading: false,
        });
        this.rpc = rpc;
        this.data = this.props.data;

        this.updateRawData();
    }

    updateRawData() {
        this.state.isLoading = true;

        if (!this.props.getSelectedIntegrations().length) {
            this.fetchDefaultData()
                .then((data) => {
                    this.state.rawData = data;
                })
                .finally(() => {
                    this.state.isLoading = false;
                });
        } else {
            this.fetchData()
                .then((data) => {
                    this.state.rawData = data;
                })
                .finally(() => {
                    this.state.isLoading = false;
                });
        }
    }

    _triggerUpdate() {
        useEffect(
            () => {
                this.updateRawData();
            },
            () => [this.props.updateKey]
        );
    }

    fetchData() {
        throw new Error('fetchData() must be implemented by subclasses');
    }

    fetchDefaultData() {
        throw new Error('fetchDefaultData() must be implemented by subclasses');
    }
}
