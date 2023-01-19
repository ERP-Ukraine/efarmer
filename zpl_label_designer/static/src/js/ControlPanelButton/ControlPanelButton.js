/** @odoo-module **/
import Widget from 'web.Widget';

export const ControlPanelButtonWidget = Widget.extend({
  template: 'zpl_label_designer.ControlPanelButton',

  events: _.extend({}, Widget.prototype.events, {
    /* No events for now */
  }),

  init: function (parent, button, object) {
    this._super(parent);
    this.button = button;
    this.object = object;
  },
});
