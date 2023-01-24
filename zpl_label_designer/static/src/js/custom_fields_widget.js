/** @odoo-module **/
import Widget from 'web.Widget';

import { _t } from '@web/core/l10n/translation';

export const CustomFieldsWidget = Widget.extend({
  template: 'zpl_label_designer.CustomFieldsWidget',

  events: _.extend({}, Widget.prototype.events, {
    'change .zpl-custom-field-select': '_onCustomFieldChange',
    'click button': '_onButtonClick',
  }),

  init: function (parent, fields, callback) {
    this._super(parent);

    this.fields = [fields];

    // Callback is called when the user clicks on the button (to add the custom field)
    this.callback = callback;
  },

  _onCustomFieldChange: function (e) {
    const newValue = e.target.value;
    const selectionIndex = Number(e.target.dataset.index);

    // Remove all selections with index greater than current selection
    const selectionEles = document.querySelectorAll('.zld-custom-field-selections select');
    Array.from(selectionEles).slice(selectionIndex + 1).forEach((el) => el.remove());
    this.fields = this.fields.slice(0, selectionIndex + 1);

    // Check if new value is many2one field
    const field = this.fields[selectionIndex].find((f) => f.name === newValue);

    if (field && field.type === 'many2one') {
      // Fetch related model fields and append to new select element
      this._rpc({
        model: 'zld.label',
        method: 'get_allowed_fields',
        args: [[this.getParent().record.res_id], field.comodel],
      }).then((fields) => {
        const containerEl = this.el.querySelector('.zld-custom-field-selections');

        // Create new select element with new fields
        const selectEl = document.createElement('select');
        selectEl.classList.add('o_input', 'o_field_widget', 'col-md-3', 'mr-2');
        selectEl.dataset.index = selectionIndex + 1;

        // Add empty option
        const emptyOptionEl = document.createElement('option');
        emptyOptionEl.value = '';
        emptyOptionEl.innerText = 'Select Field';
        selectEl.appendChild(emptyOptionEl);

        // Add options for each field
        fields.forEach((f) => {
          const optionEl = document.createElement('option');
          optionEl.value = f.name;
          optionEl.innerText = f.label + (f.type === 'many2one' ? ' →' : '');

          selectEl.appendChild(optionEl);
        });

        // Listen for changes on new select element
        selectEl.addEventListener('change', this._onCustomFieldChange.bind(this));

        containerEl.append(selectEl);

        // Save fields for later use
        this.fields.push(fields);
      });
    }
  },

  _onButtonClick: function (e) {
    e.preventDefault();

    const selectionEles = document.querySelectorAll('.zld-custom-field-selections select');
    const selections = Array.from(selectionEles).map((el) => el.value).filter((el) => el);

    if (!selections.length) {
      alert(_t('Please select a field to add'));
      return;
    }

    // Call callback with joined selections
    this.callback(selections.join('.'));
  },
});
