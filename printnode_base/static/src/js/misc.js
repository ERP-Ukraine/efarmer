/** @odoo-module **/

/*
This file includes few snippets related to storing/clearing information about workstation
printers/scales. A bit 'hacky' thing :)
*/

import rpc from 'web.rpc';
import session from 'web.session';
import { browser } from '@web/core/browser/browser';
import { useService } from '@web/core/utils/hooks';
import { registry } from '@web/core/registry';


class DirectPrintMainComponent extends owl.Component {
    /*
    This component manages workstation devices
    */
    constructor(parent, props) {
        super(...arguments);

        this.user = useService('user');
    }

    async willStart() {
        if (session.dpc_company_enabled) {
            // Check if UUID is already set
            let workstationId = browser.localStorage.getItem('printnode_base.workstation_id');

            if (workstationId) {
                // Convert to int
                workstationId = parseInt(workstationId);

                // Check if record with workstationId is exist in db
                await rpc.query({
                    model: 'printnode.workstation',
                    method: 'search_count',
                    args: [[['id', '=', workstationId]]],
                }).then((result) => {
                    if (result) {
                        // Set workstation ID to context
                        this.user.updateContext({ 'printnode_workstation_id': workstationId });
                    } else {
                        console.log('Workstation with such ID was not found!');
                    }
                });
            }
        }
    }

};

Object.assign(DirectPrintMainComponent, {
    props: {},
    template: owl.tags.xml`<div/>`,
});

registry.category('main_components').add(
    'DirectPrintMainComponent',
    { Component: DirectPrintMainComponent, props: {} }
);
