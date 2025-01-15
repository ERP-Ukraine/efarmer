/** @odoo-module **/

import fieldRegistry from 'web.field_registry';
import { FieldText } from 'web.basic_fields';

const DENSITY = {
  152: '6dpmm',
  203: '8dpmm',
  300: '12dpmm',
  600: '24dpmm',
};

const LabelPreviewField = FieldText.extend({
  _renderEdit: function () {
    this._renderZPLPreview();
  },

  _renderReadonly: function () {
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

          this.$el.prepend(imageEl);
        });
      // TODO: Add error catching
    }
  },
});

fieldRegistry.add('zld_label_preview', LabelPreviewField);
