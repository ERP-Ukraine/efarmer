/** @odoo-module **/

import FormController from 'web.FormController';
import FormView from 'web.FormView';
import viewRegistry from 'web.view_registry';
import rpc from 'web.rpc';

const LabelFormController = FormController.extend({
  init: function () {
    this._super(...arguments);

    // Load URL from server
    rpc.query({
      model: 'zld.label',
      method: 'get_label_designer_url',
    }).then((url) => {
      this.designerURL = url;
    });
  },

  _onCreate: function (ev) {
    ev.preventDefault();
    window.open(this.designerURL, '_blank');
  },
});

const LabelFormView = FormView.extend({
  config: _.extend({}, FormView.prototype.config, {
    Controller: LabelFormController,
  }),
});

viewRegistry.add('zld_label_form_view', LabelFormView);

export default LabelFormView;
