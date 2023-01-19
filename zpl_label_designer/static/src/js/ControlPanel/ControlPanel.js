/** @odoo-module **/
import Widget from 'web.Widget';

import { ControlPanelButtonGroupWidget } from '../ControlPanelButtonGroup/ControlPanelButtonGroup';
import { OBJECT_CONTROLS } from '../constants';

export const ControlPanelWidget = Widget.extend({
  template: 'zpl_label_designer.ControlPanel',

  events: _.extend({}, Widget.prototype.events, {
    /* No events for now */
  }),

  init: function (parent, canvas) {
    this._super(parent);

    this.canvas = canvas;

    /* Initial possition for debug */
    this.top = 50;
    this.left = 50;

    // Groups of buttons to render
    this.groups = [];

    // State
    this.visible = false;
  },

  show: function () {
    const changed = this._updatePosition();

    if (changed) {
      this.renderElement();
    }

    this.do_show();
    this.visible = true;
  },

  hide: function () {
    this.do_hide();
    this.visible = false;
  },

  toggle: function () {
    if (this.visible) {
      this.hide();
    } else {
      this.show();
    }
  },

  update: function (object) {
    this.object = object;

    if (object) {
      this.groups = OBJECT_CONTROLS[object.type] || [];

      this._updatePosition();
      this.renderElement();
    }
  },

  getStyle: function () {
    return `top: ${this.top}px; left: ${this.left}px;`;
  },

  renderElement: function () {
    this._super();

    // Render groups
    this.groups.forEach((group) => {
      const groupWidget = new ControlPanelButtonGroupWidget(
        this, group.name, group.controls, this.object);
      groupWidget.appendTo(this.$('.zld-control-panel-button-groups'));
    });
  },

  _updatePosition: function () {
    const obj = this.object;
    let changed = false;

    let newTop = obj.canvas._offset.top - 10;
    let newLeft = obj.canvas._offset.left + 10;

    // Show the control panel on the right of the object
    if (obj.angle === 0) {
      newTop += obj.aCoords.tr.y;
      newLeft += obj.aCoords.tr.x;
    } else if (obj.angle === 90) {
      newTop += obj.aCoords.tl.y;
      newLeft += obj.aCoords.tl.x;
    } else if (obj.angle === 180) {
      newTop += obj.aCoords.bl.y;
      newLeft += obj.aCoords.bl.x;
    } else if (obj.angle === 270) {
      newTop += obj.aCoords.br.y;
      newLeft += obj.aCoords.br.x;
    }

    changed = this.top !== newTop || this.left !== newLeft;

    this.top = newTop;
    this.left = newLeft;

    return changed;
  },

});
