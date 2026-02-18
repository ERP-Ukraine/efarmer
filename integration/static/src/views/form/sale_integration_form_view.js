/** @odoo-module **/

import { registry } from '@web/core/registry';
import { formView } from '@web/views/form/form_view';
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { FormController } from '@web/views/form/form_controller';
import { Layout } from "@web/search/layout";

export class SaleIntegrationControlPanel extends ControlPanel { }

SaleIntegrationControlPanel.template = 'integration.SaleIntegrationControlPanel';

export class SaleIntegrationLayout extends Layout {
    setup() {
        super.setup();

        this.components = {
            ...this.components,
            ControlPanel: SaleIntegrationControlPanel,
        };
    }
}

export class SaleIntegrationFormController extends FormController { }

SaleIntegrationFormController.components = {
    ...FormController.components,
    Layout: SaleIntegrationLayout,
}

registry.category('views').add('sale_integration_form_view', {
    ...formView,
    Controller: SaleIntegrationFormController,
});
