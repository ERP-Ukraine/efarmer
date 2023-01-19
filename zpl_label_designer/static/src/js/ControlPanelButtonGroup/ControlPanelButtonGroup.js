/** @odoo-module **/
import Widget from 'web.Widget';

import { ControlPanelButtonWidget } from '../ControlPanelButton/ControlPanelButton';

export const ControlPanelButtonGroupWidget = Widget.extend({
  template: 'zpl_label_designer.ControlPanelButtonGroup',

  events: _.extend({}, Widget.prototype.events, {
    'click .zld-control-panel-button': '_onClick',
  }),

  init: function (parent, name, buttons, object) {
    this._super(parent);

    this.name = name;
    this.buttons = buttons;
    this.object = object;
  },

  start: function () {
    this._super();

    // Render buttons
    this.buttons.forEach((button) => {
      const buttonWidget = new ControlPanelButtonWidget(this, button, this.object);
      buttonWidget.appendTo(this.$('.zld-control-panel-group-buttons'));
    });
  },

  _onClick: function (ev) {
    const button = this.buttons.find((b) => b.name === ev.currentTarget.dataset.name);

    if (button.toggle || button.isActive(this.object)) {
      button.clickHandler(this.object);

      this.object.canvas.renderAll();

      // Re-render group of buttons to show buttons in the correct state
      this.renderElement();
      this.start();
    }
  },
});
