/** @odoo-module **/

import FormView from 'web.FormView';
import FormController from 'web.FormController';
import viewRegistry from 'web.view_registry';

const SaleIntegrationFormController = FormController.extend({
    // This approach doesn't work for form views because Odoo hardcodes the buttons
    // buttons_template: 'SaleIntegrationFormView.buttons',

    renderButtons: function ($node) {
        // Call parent method
        this._super.apply(this, arguments);
    
        // Append button after other buttons in control panel (for both edit and view modes)
        this.$buttons.find('.o_form_buttons_view').append(
            $('<a>', {
                class: 'btn btn-outline-success text-uppercase',
                href: 'https://support.ventor.tech/',
                target: '_blank',
                text: 'Documentation & Support',
            })
        );
        this.$buttons.find('.o_form_buttons_edit').append(
            $('<a>', {
                class: 'btn btn-outline-success text-uppercase',
                href: 'https://support.ventor.tech/',
                target: '_blank',
                text: 'Documentation & Support',
            })
        );
    },
});

const SaleIntegrationFormView = FormView.extend({
  config: _.extend({}, FormView.prototype.config, {
    Controller: SaleIntegrationFormController,
  }),
});

viewRegistry.add('sale_integration_form_view', SaleIntegrationFormView);

export default SaleIntegrationFormView;
