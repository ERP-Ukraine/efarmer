/** @odoo-module **/

// import ajax from 'web.ajax';
import rpc from 'web.rpc';
import session from 'web.session';

import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

// import WORKSTATION_DEVICES from './constants';

const systrayRegistry = registry.category('systray');
const MANAGER_GROUP = 'printnode_base.printnode_security_group_manager';

export class PrintnodeStatusMenu extends owl.Component {
    setup() {
        this.user = useService('user');
        this.state = owl.useState({
            limits: [],
            devices: [],
            releases: [],
            rateUsURL: null,
            isManager: false,
            loaded: false,
            printnodeEnabled: session.dpc_user_enabled,
        });
    }

    async willStart() {
        return this._fetchData(true);
    }

    async _fetchData(onlyReleases = false) {
        this.state.loaded = false;

        if (this.state.printnodeEnabled) {
            // We check if current user has Manager group to make some elements of status menu
            // visible only for managers
            this.state.isManager = await session.user_has_group(MANAGER_GROUP);

            const data = await rpc.query({
                model: 'printnode.base',
                method: 'get_status',
                kwargs: { 'only_releases': onlyReleases },
                context: session.user_context,
            });

            this.state.limits = data.limits;
            this.state.releases = data.releases;
            this.state.devices = data.devices;
            this.state.rateUsURL = this._prepareRateUsURL();
        }
        this.state.loaded = true;
    }

    _prepareRateUsURL() {
        // Rate Us URL
        let odooVersion = odoo.info.server_version;
        // This attribute can include some additional symbols we do not need here (like 12.0e+)
        odooVersion = odooVersion.substring(0, 4);

        return `https://apps.odoo.com/apps/modules/${odooVersion}/printnode_base/#ratings`;
    }

    _onClickDropdownToggle(ev) {
        ev.preventDefault();

        if (this.state.isOpen) {
            this.state.isOpen = false;
        } else {
            this.state.isOpen = true;
            this._fetchData();
        }
    }

    _onClickDefaultDevicesCollapse(ev) {
        /*
        This is adapted logic from bootstrap collapse. We need to duplicate it because click will
        be captured by this component and not by bootstrap collapse
        */
        ev.preventDefault();
        ev.stopPropagation();

        const control = ev.target.attributes['aria-controls'].value;
        const collapse = document.getElementById(control);

        if (collapse.classList.contains('show')) {
            collapse.classList.remove('show');
        } else {
            collapse.classList.add('show');
        }
    }
}

Object.assign(PrintnodeStatusMenu, {
    props: {},
    template: 'printnode_base.StatusMenu',
});

systrayRegistry.add('printnode_base.StatusMenu', {
    Component: PrintnodeStatusMenu,
});