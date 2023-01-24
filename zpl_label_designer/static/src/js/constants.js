/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';

const MODULE_STATIC_PATH = '/zpl_label_designer/static/src/images';

// Removed 'splitWords'. Need to check if everythings is ok.
const PROPERTIES_TO_SAVE = ['id', 'editable', 'snapAngle', 'isQR', 'isBarcode', 'aCoords', 'class'];
const CONTROL_CORNER_SIZE = 24;
// This is splitters we used to not split the text into lines (because of different fonts)
const WORD_JOINERS = /[]/;

const FONTS = ['Roboto Condensed', 'Roboto Mono'];
const GOOGLE_FONTS = [['Roboto Condensed', { weight: 700 }], ['Roboto Mono', {}]];

const OBJECT_CONTROLS = {
  textbox: [
    {
      name: 'Barcode',
      controls: [
        {
          name: 'barcode',
          tooltip: _t('Render as barcode'),
          image: `${MODULE_STATIC_PATH}/upc.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/upc-inactive.svg`,
          clickHandler: (object) => {
            object.set({ isBarcode: !object.isBarcode, isQR: false });
          },
          toggle: true,
          isActive: (object) => object.isBarcode,
        },
        {
          name: 'qr',
          tooltip: _t('Render as QR'),
          image: `${MODULE_STATIC_PATH}/qr-code.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/qr-code-inactive.svg`,
          clickHandler: (object) => {
            object.set({ isQR: !object.isQR, isBarcode: false });
          },
          toggle: true,
          isActive: (object) => object.isQR,
        },
      ],
    },
    {
      name: 'Alignment',
      controls: [
        {
          name: 'left',
          tooltip: _t('Align left'),
          image: `${MODULE_STATIC_PATH}/text-left.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/text-left-inactive.svg`,
          clickHandler: (object) => {
            object.set({ textAlign: 'left' });
          },
          toggle: true,
          isActive: (object) => object.textAlign === 'left',
        },
        {
          name: 'center',
          tooltip: _t('Align center'),
          image: `${MODULE_STATIC_PATH}/text-center.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/text-center-inactive.svg`,
          clickHandler: (object) => {
            object.set({ textAlign: 'center' });
          },
          toggle: true,
          isActive: (object) => object.textAlign === 'center',
        },
        {
          name: 'right',
          tooltip: _t('Align right'),
          image: `${MODULE_STATIC_PATH}/text-right.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/text-right-inactive.svg`,
          clickHandler: (object) => {
            object.set({ textAlign: 'right' });
          },
          toggle: true,
          isActive: (object) => object.textAlign === 'right',
        },
      ],
    },
    {
      name: 'Font',
      controls: [
        {
          name: 'font',
          tooltip: _t('Change font'),
          image: `${MODULE_STATIC_PATH}/file-font.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/file-font.svg`,
          clickHandler: (object) => {
            const currentFont = object.fontFamily;

            // Find next font
            const currentFontIndex = FONTS.indexOf(currentFont);
            const newFontIndex = currentFontIndex < FONTS.length - 1 ? currentFontIndex + 1 : 0;
            const newFont = FONTS[newFontIndex];

            object.set({ styles: {}, fontFamily: newFont });
          },
          isActive: () => true,
        },
      ],
    },
  ],
  rect: [
    {
      name: 'Fill',
      controls: [
        {
          name: 'fill',
          tooltip: _t('Control fill of the rectangle'),
          image: `${MODULE_STATIC_PATH}/square-fill.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/square-fill-inactive.svg`,
          toggle: true,
          clickHandler: (object) => {
            object.set({ fill: object.fill === null ? 'black' : null, dirty: true });
          },
          isActive: (object) => object.fill !== null,
        },
      ],
    },
    {
      name: 'Stroke',
      controls: [
        {
          name: 'increase',
          tooltip: _t('Increase stroke width'),
          image: `${MODULE_STATIC_PATH}/plus-square.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/plus-square-inactive.svg`,
          clickHandler: (object) => {
            // Have to mark as dirty to rerender object on canvas
            object.set({
              strokeWidth: ++object.strokeWidth,
              dirty: true,
            });
          },
          isActive: (object) => {
            const width = object.width * object.scaleX;
            const height = object.height * object.scaleY;

            return width > object.strokeWidth && height > object.strokeWidth;
          },
        },
        {
          name: 'decrease',
          tooltip: _t('Decrease stroke width'),
          image: `${MODULE_STATIC_PATH}/dash-square.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/dash-square-inactive.svg`,
          clickHandler: (object) => {
            // Have to mark as dirty to rerender object on canvas
            object.set({
              strokeWidth: --object.strokeWidth,
              dirty: true,
            });
          },
          isActive: (object) => object.strokeWidth > 1,
        },
      ],
    },
  ],
  line: [
    {
      name: 'Stroke',
      controls: [
        {
          name: 'increase',
          tooltip: _t('Increase stroke width'),
          image: `${MODULE_STATIC_PATH}/plus-square.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/plus-square-inactive.svg`,
          clickHandler: (object) => {
            // Have to mark as dirty to rerender object on canvas
            object.set({
              strokeWidth: ++object.strokeWidth,
              dirty: true,
            });
          },
          isActive: () => true,
        },
        {
          name: 'decrease',
          tooltip: _t('Decrease stroke width'),
          image: `${MODULE_STATIC_PATH}/dash-square.svg`,
          imageInactive: `${MODULE_STATIC_PATH}/dash-square-inactive.svg`,
          clickHandler: (object) => {
            // Have to mark as dirty to rerender object on canvas
            object.set({
              strokeWidth: --object.strokeWidth,
              dirty: true,
            });
          },
          isActive: (object) => object.strokeWidth > 1,
        },
      ],
    },
  ],
};

const SERVER_DOWN_MESSAGE = _t(`ZPL Converter Server is on maintenance. Try again in a few minutes.
If the issue will not be solved, please, drop us an email at support@ventor.tech`);

export {
  MODULE_STATIC_PATH,
  OBJECT_CONTROLS,
  SERVER_DOWN_MESSAGE,
  PROPERTIES_TO_SAVE,
  CONTROL_CORNER_SIZE,
  WORD_JOINERS,
  FONTS,
  GOOGLE_FONTS,
};
