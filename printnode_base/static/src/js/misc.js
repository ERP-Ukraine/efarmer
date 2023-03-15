/** @odoo-module **/

/*
This file includes few snippets related to storing/clearing information about workstation
printers/scales. A bit 'hacky' thing :)
*/

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
            let deviceUUID = browser.localStorage.getItem('printnode_base.uuid');

            if (!deviceUUID) {
                // Create new UUID
                deviceUUID = uuid();
                browser.localStorage.setItem('printnode_base.uuid', deviceUUID);
            }

            // Set UUID to context
            this.user.updateContext({ 'printnode_workstation_uuid': deviceUUID });
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

/**
 * Generate a unique identifier (64 bits) in hexadecimal.
 *
 * @returns {string}
 */
function uuid() {
    const array = new Uint8Array(8);
    window.crypto.getRandomValues(array);
    // Uint8Array to hex
    return [...array].map((b) => b.toString(16).padStart(2, '0')).join('');
}
