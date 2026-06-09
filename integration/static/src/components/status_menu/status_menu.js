/* @odoo-module */

import { Component, onWillRender, useState } from "@odoo/owl";

import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";


function useIntegrationStatusMenuSystray() {
    const ui = useState(useService("ui"));
    return {
        class: "o-integration-IntegrationStatusMenu-class",
        get contentClass() {
            return `d-flex flex-column flex-grow-1 bg-view ${ui.isSmall ? "overflow-auto w-100 mh-100" : ""
                }`;
        },
        get menuClass() {
            return `p-0 o-integration-IntegrationStatusMenu ${ui.isSmall
                ? "o-integration-systrayFullscreenDropdownMenu start-0 w-100 mh-100 d-flex flex-column mt-0 border-0 shadow-lg"
                : ""
                }`;
        },
    };
}

export class IntegrationStatusMenu extends Component {
    static components = { Dropdown };
    static props = [];
    static template = "integration.IntegrationStatusMenu";

    setup() {
        this.integrationStatusMenuSystray = useIntegrationStatusMenuSystray();
        this.dropdown = useDropdownState();
        this.ui = useState(useService("ui"));
        this.state = useState({
            integrations: [],
            activityCounterFailed: 0,
            activityCounterUnprocessed: 0,
            activityVisible: false,
            isOpen: false,
            isLoaded: false,
            isManager: false,
        });

        this.orm = useService("orm");
        this.user = user;
        this.action = useService("action");

        onWillRender(async () => {
            if (window.QUnit) {
                // Do nothing during JS tests
                return;
            }

            this.state.isManager = await this.user.hasGroup('integration.group_integration_manager');

            if (!this.state.isLoaded) {
                const data = await this.orm.call(
                    "sale.integration",
                    "get_status_menu_data",
                    [],
                    {});

                this.state.integrations = data;
                this.state.activityCounterFailed = data.reduce((acc, value) => { return acc + value.failed_jobs_count || 0; }, 0);
                this.state.activityCounterUnprocessed = data.reduce((acc, value) => { return acc + value.unprocessed_orders_count || 0; }, 0);
                this.state.activityVisible = this.state.activityCounterFailed > 0 || this.state.activityCounterUnprocessed > 0;
                this.state.isLoaded = true;
            }
        });
    }

    formatCount(count) {
        return count > 99 ? '99+' : count.toString();
    }

    async beforeOpen() {
        const data = await this.orm.call(
            "sale.integration",
            "get_status_menu_data",
            [],
            {});

        this.state.integrations = data;
        this.state.activityCounterFailed = data.reduce((acc, value) => { return acc + value.failed_jobs_count || 0; }, 0);
        this.state.activityCounterUnprocessed = data.reduce((acc, value) => { return acc + value.unprocessed_orders_count || 0; }, 0);
        this.state.activityVisible = this.state.activityCounterFailed > 0 || this.state.activityCounterUnprocessed > 0;
    }

    async openIntegration(integrationId) {
        this.close();
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Integration'),
            res_model: 'sale.integration',
            res_id: integrationId,
            views: [[false, 'form']],
        });
    }

    async openOrders(integrationId) {
        this.close();
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Orders'),
            res_model: 'sale.integration.input.file',
            views: [[false, 'list'], [false, 'form']],
            domain: [
                ['si_id', '=', integrationId],
            ],
        });
    }

    async openProducts(integrationId) {
        this.close();
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Products'),
            res_model: 'integration.product.template.mapping',
            views: [[false, 'list'], [false, 'form']],
            domain: [
                ['integration_id', '=', integrationId],
            ],
            context: {
                default_integration_id: integrationId,
            },
        });
    }

    async openFailedJobs(integrationId) {
        this.close();
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Failed Jobs'),
            res_model: 'queue.job',
            views: [[false, 'list'], [false, 'form']],
            domain: [
                ['state', '=', 'failed'],
                ['integration_id', '=', integrationId]
            ],
            context: {
                search_default_state: 1,
            },
        });
    }

    async openUnprocessedOrders(integrationId) {
        this.close();
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Unprocessed Orders'),
            res_model: 'sale.integration.input.file',
            views: [[false, 'list'], [false, 'form']],
            domain: [
                ['si_id', '=', integrationId],
            ],
            context: {
                search_default_without_sales_order: true,
            },
        });
    }

    async openMissingMappings(integrationId, modelName) {
        this.close();
        const mappingModel = this.orm.call(modelName, 'fields_get', [['_mapping_fields']]);

        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Missing Mappings'),
            res_model: modelName,
            views: [[false, 'list'], [false, 'form']],
            domain: [
                ['integration_id', '=', integrationId],
            ],
            context: {
                default_integration_id: integrationId,
            },
        });
    }

    close() {
        this.dropdown.close();
    }
}

registry
    .category("systray")
    .add("integration.IntegrationStatusMenu", { Component: IntegrationStatusMenu }, { sequence: 25 });
