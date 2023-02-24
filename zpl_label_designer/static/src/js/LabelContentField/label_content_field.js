/** @odoo-module **/

import config from 'web.config';
import fieldRegistry from 'web.field_registry';
import { FieldText } from 'web.basic_fields';

const DENSITY = {
  152: '6dpmm',
  203: '8dpmm',
  300: '12dpmm',
  600: '24dpmm',
};

const LabelContentField = FieldText.extend({
  init: function (parent) {
    // Save form object for later use
    this.parent = parent;

    this._super(...arguments);
  },

  _renderZPLContent: function () {
    // Show raw label content only in debug mode
    if (config.isDebug()) {
      const div = document.createElement('div');
      div.classList.add('zld-content-container', 'mb-4');
      div.textContent = this._formatValue(this.value);
      div.readOnly = true;

      // Select preview content on double click
      div.addEventListener('dblclick', (e) => {
        e.preventDefault();
        // Select all text in the content element
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(div);
        selection.removeAllRanges();
        selection.addRange(range);
      });

      this.$el.append(div);
    }
  },

  _renderEdit: function () {
    this._renderZPLContent();
    this._renderZPLPreview();
  },

  _renderReadonly: function () {
    this._renderZPLContent();
    this._renderZPLPreview();
  },

  _renderZPLPreview: function () {
    if (this.record.data.preview) {
      // TODO: Move dpmm to readonly calculated field on backend?
      const dpmm = DENSITY[this.record.data.dpi];
      const width = this.record.data.width;
      const height = this.record.data.height;
      const labelaryUrl = `https://api.labelary.com/v1/printers/${dpmm}/labels/${width}x${height}/0/`;

      const formData = new FormData();
      formData.append('file', this.value);

      fetch(labelaryUrl, { method: 'POST', body: formData })
        .then((response) => response.blob())
        .then((blob) => {
          const previewURL = URL.createObjectURL(blob);

          const imageEl = document.createElement('img');
          imageEl.classList.add('border');
          imageEl.src = previewURL;

          this.$el.append(imageEl);
        });
      // TODO: Add error catching
    }
  },
});

fieldRegistry.add('zld_label_content', LabelContentField);
