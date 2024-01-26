odoo.define('integration.status_menu', function (require) {
    "use strict";

    var core = require('web.core');
    var SystrayMenu = require('web.SystrayMenu');
    var Widget = require('web.Widget');
    var QWeb = core.qweb;

    var ActionMenu = Widget.extend({
        template: 'integration_status_menu',

        events: {
            'show.bs.dropdown': '_onIntegrationStatusShow',
        },

        start: function () {
            this._$integrationsPreview = this.$('.o_integrations_systray_dropdown_items');
            this._updateIntegrationsPreview();
            return this._super();
        },

        _getIntegrationsData: function () {
            var self = this;

            return self._rpc({
                model: 'sale.integration',
                method: 'systray_get_integrations',
                args: [],
                kwargs: {},
            }).then(function (data) {
                self._integrations = data;
                self.activityCounterFailed = _.reduce(data, function (total_count, p_data) { return total_count + p_data.failed_jobs_count || 0; }, 0);
                self.activityCounterMissing = _.reduce(data, function (total_count, p_data) { return total_count + p_data.missing_mappings_count || 0; }, 0);
                self.$('.o_notification_counter').text(self.activityCounterFailed + ' / ' + self.activityCounterMissing);
            });
        },

        _updateIntegrationsPreview: function () {
            var self = this;
            self._getIntegrationsData().then(function (){
                self._$integrationsPreview.html(QWeb.render('integration_status_menu_item', {
                    widget: self
                }));
            });
        },

        _onIntegrationStatusShow: function () {
             this._updateIntegrationsPreview();
        },

    });

    SystrayMenu.Items.push(ActionMenu);

    return ActionMenu;
});
