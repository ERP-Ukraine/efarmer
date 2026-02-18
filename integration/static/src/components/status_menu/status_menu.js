/* @odoo-module */

import { Component, onWillRender, useState } from "@odoo/owl";

import { Dropdown } from "@web/core/dropdown/dropdown";
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
        this.ui = useState(useService("ui"));
        this.state = useState({
            integrations: [],
            activityCounterFailed: 0,
            activityCounterMissing: 0,
            activityCounter: '',
            activityVisible: false,
            isOpen: false,
            isLoaded: false,
            isManager: false,
        });

        this.orm = useService("orm");
        this.user = user;

        onWillRender(async () => {
            if (window.QUnit) {
                // Do nothing during JS tests
                return;
            }

            this.state.isManager = await this.user.hasGroup('integration.group_integration_manager');

            if (!this.state.isLoaded) {
                const data = await this.orm.call(
                    "sale.integration",
                    "systray_get_integrations",
                    [],
                    {});

                this.state.integrations = data;
                this.state.activityCounterFailed = data.reduce((acc, value) => { return acc + value.failed_jobs_count || 0; }, 0);
                this.state.activityCounterMissing = data.reduce((acc, value) => { return acc + value.missing_mappings_count || 0; }, 0);
                this.state.activityCounter = this.state.activityCounterFailed + ' / ' + this.state.activityCounterMissing;
                this.state.activityVisible = this.state.activityCounterFailed > 0 || this.state.activityCounterMissing > 0;
                this.state.isLoaded = true;
                this.state.typeApis = [...new Set(data.map(i => i.type_api))];
            }
        });
    }

    async beforeOpen() {
        const data = await this.orm.call(
            "sale.integration",
            "systray_get_integrations",
            [],
            {});

        this.state.integrations = data;
        this.state.activityCounterFailed = data.reduce((acc, value) => { return acc + value.failed_jobs_count || 0; }, 0);
        this.state.activityCounterMissing = data.reduce((acc, value) => { return acc + value.missing_mappings_count || 0; }, 0);
        this.state.activityCounter = this.state.activityCounterFailed + ' / ' + this.state.activityCounterMissing;
        this.state.activityVisible = this.state.activityCounterFailed > 0 || this.state.activityCounterMissing > 0;
        this.state.typeApis = [...new Set(data.map(i => i.type_api))];
    }

    getRateUsURL(typeApi) {
        // Rate Us URL
        let odooVersion = odoo.info.server_version;
        // This attribute can include some additional symbols we do not need here (like 12.0e+)
        odooVersion = odooVersion.substring(0, 4);

        const url = `https://apps.odoo.com/apps/modules/${odooVersion}/integration_${typeApi}/#ratings`;

        return url;
    }

    getModuleIcon(typeApi) {
        return `/integration_${typeApi}/static/description/icon.png`;
    }

    close() {
        // hack: click on window to close dropdown, because we use a dropdown
        // without dropdownitem...
        document.body.click();
    }
}

registry
    .category("systray")
    .add("integration.IntegrationStatusMenu", { Component: IntegrationStatusMenu }, { sequence: 25 });
