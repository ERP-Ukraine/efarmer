/** @odoo-module **/

import config from 'web.config';
import AbstractField from 'web.AbstractField';
import fieldRegistry from 'web.field_registry';

import { FONTS, GOOGLE_FONTS, PROPERTIES_TO_SAVE, WORD_JOINERS } from './constants';
import { CustomFieldsWidget } from './custom_fields_widget';
import { ControlPanelWidget } from './ControlPanel/ControlPanel';

const LabelEditorField = AbstractField.extend({
  template: 'zpl_label_designer.LabelEditor',

  events: _.extend({}, AbstractField.prototype.events, {
    'click #zld-show-grid': '_onShowGridClick',
    'click .zld-add-text': '_onAddTextClick',
    'click #zld-add-rectangle': '_onAddRectClick',
    'click #zld-add-line': '_onAddLineClick',
  }),
  custom_events: _.extend({}, AbstractField.prototype.custom_events, {}),

  init: function (parent) {
    this._super(...arguments);

    // Save form object for later use
    this.parent = parent;

    this.snapLine = null;

    // This variable will be used in grid and snap features
    this.DPMM = Math.round(this.record.data.dpi / 25.4);

    // Do not consider space as a word joiner
    // This way text breaks only when the user types Enter
    fabric.Textbox.prototype._wordJoiners = WORD_JOINERS;
  },

  _renderEdit: function () {
    this._setupEditor();
    this.el.querySelector('.control-panel').classList.remove('d-none');
  },

  _renderReadonly: function () {
    this._setupEditor(true);
    this.$el.find('.zld-buttons-panel').hide();
  },

  _setupEditor: function (readonly = false) {
    if (!this.record.data.id) {
      // No record yet, do not render anything
      return;
    }

    // Load custom fonts before the canvas initialization
    const observers = GOOGLE_FONTS.map((font) => {
      const observer = new FontFaceObserver(font[0], font[1]);
      return observer.load();
    });

    Promise.all(observers)
      .then(() => {
        // Initialize canvas
        const width = this.record.data.width * this.record.data.dpi;
        const height = this.record.data.height * this.record.data.dpi;

        this.canvasEl = this.el.querySelector('canvas');

        this.canvas = new fabric.Canvas(
          this.canvasEl,
          {
            width: width,
            height: height,
            snapThreshold: 45,
            snapAngle: 90,
          },
        );

        // Load content
        if (this.record.data.blob) {
          // TODO: Need to provide a check for a correct JSON string
          this.canvas.loadFromJSON(this.record.data.blob, () => {
            this.canvas.forEachObject((object) => {
              object.selectable = !readonly;

              // Disable rotation for rects
              if (object.type === 'rect') {
                object.setControlsVisibility({ mtr: false });
              }

              // Detect if we want to split by spaces. It is used mostly for QR only
              // object._wordJoiners = object.splitWords ? DEFAULT_WORD_JOINERS : WORD_JOINERS;
            });
          });
        }

        // Load different parts required for editor
        if (!readonly) {
          this.controlPanel = new ControlPanelWidget(this, this.canvas);
          this.controlPanel.appendTo(this.el);

          // this._loadControlIcons();
          this._addQuickFieldsButtons();
          this._addEvents();
          this._addCustomFields();
        }

        // Debug logging
        if (config.isDebug()) {
          console.log(this);
        }
      });
  },

  _renderGrid: function () {
    // Remove old lines
    this._removeGrid();

    for (let i = 1; i < Math.round(this.canvas.width / this.DPMM); i++) {
      this.canvas.insertAt(
        new fabric.Line(
          [i * this.DPMM, 0, i * this.DPMM, this.canvas.height],
          { type: 'line', stroke: '#eee', strokeWidth: 0.5, selectable: false, class: 'grid' }),
        0);

      this.canvas.insertAt(
        new fabric.Line(
          [0, i * this.DPMM, this.canvas.width, i * this.DPMM],
          { type: 'line', stroke: '#eee', strokeWidth: 0.5, selectable: false, class: 'grid' }),
        0);
    }
  },

  _removeGrid: function () {
    if (this.canvas) {
      this.canvas
        .getObjects()
        .filter((o) => o.class === 'grid')
        .forEach((o) => this.canvas.remove(o));
    }
  },

  _updateSnapLine: function (linePoints) {
    // Remove existing snap line
    this._resetSnapLine();

    // Add new snap line to canvas
    this.snapLine = new fabric.Line(linePoints, { class: 'snap', stroke: '#dddddd', strokeWidth: 1 });
    this.canvas.add(this.snapLine);
  },

  _addQuickFieldsButtons: function () {
    const quickFields = this.parent.settings.quick_fields || {};

    // Clean buttons container
    const containerEl = this.el.querySelector('.zld-quick-buttons');
    while (containerEl.firstChild) {
      containerEl.removeChild(containerEl.firstChild);
    }

    // Add new buttons
    Object.entries(quickFields).forEach((f) => {
      const [field, value] = f;
      const buttonEl = document.createElement('button');
      buttonEl.innerText = field;
      buttonEl.classList.add('btn', 'btn-outline-primary', 'mr-2', 'mb-2', 'zld-add-text');
      buttonEl.dataset.value = `%%${value}%%`;

      containerEl.append(buttonEl);
    });
  },

  _addEvents: function () {
    // Listen to keyboard events
    // This is not actually a good option to listen to document events
    // but there is no other way to do it (at least for now)
    // TODO: http://fabricjs.com/events
    document.onkeydown = (e) => {
      // Notice: e.key is not fully supported in all browsers! Need to check it
      const { key } = e;

      if (key === 'Backspace' || key === 'Delete') {
        const activeObject = this.canvas.getActiveObject();

        if (activeObject && !activeObject.isEditing) {
          this.canvas.remove(activeObject);
          this.canvas.renderAll();
        }
      }
    };

    this.canvas.on('text:changed', this._onCanvasTextChanged);
    this.canvas.on('mouse:up', this._onCanvasMouseUp.bind(this));
    this.canvas.on('object:moving', this._onCanvasObjectMoving.bind(this));

    /*
    * Control panel events
    */
    this.canvas.on('mouse:down', (e) => {
      // Toggle control panel on next clicks for the same object
      if (e.target) { // Click on an object
        const selected = this.canvas.getActiveObject();

        if (selected) {
          if (selected === this.controlPanel.object) {
            this.controlPanel.toggle();
          } else {
            this.controlPanel.update(selected);
            this.controlPanel.show();
          }
        } else {
          // No object selected
          this.controlPanel.update(null);
          this.controlPanel.hide();
        }
      } else {
        // Click on the canvas
        this.controlPanel.update(null);
        this.controlPanel.hide();
      }
    });

    ['object:moving', 'object:scaling', 'object:rotating', 'object:resizing'].forEach(
      (event) => this.canvas.on(event, this.controlPanel.hide.bind(this.controlPanel)),
    );

    setTimeout(() => {
      // After a second bind scroll event to the o_form_sheet_bg element to hide control panel
      // when user scrolls the page. This is not a good solution but there is no other way
      // to do it
      const contentEl = this.el.closest('.o_content');
      const formSheetBgEl = this.el.closest('.o_form_sheet_bg');

      // There are multple element to which overflow can be applied (depends on the screen size)
      // so we need to listen for events for both of them. This is not a good solution but there
      // is no other way to do it
      if (contentEl && formSheetBgEl) {
        contentEl.addEventListener('scroll', this.controlPanel.hide.bind(this.controlPanel));
        formSheetBgEl.addEventListener('scroll', this.controlPanel.hide.bind(this.controlPanel));
      }
    }, 1500);

    this.canvas.on('text:changed', (e) => {
      this.controlPanel.update(e.target);
    });
  },

  _onCanvasMouseUp: function () {
    this._resetSnapLine();
  },

  _onCanvasObjectMoving: function () {
    const targetObject = this.canvas.getActiveObject();
    targetObject.setCoords(); // Update object coordinates

    // Remove old snap lines
    this._resetSnapLine();

    // Do nothing if object rotated
    if (targetObject.angle !== 0) return;

    // Do nothing if user selects a group of objects
    if (targetObject.type === 'activeSelection') return;

    this.canvas.forEachObject((object) => {
      // Skip grid and snap lines
      if (object.class === 'grid' || object.class === 'snap') return;
      // Skip self
      if (object === targetObject) return;
      // Skip rotated objects
      if (object.angle !== 0) return;

      const { oCoords } = object;
      const tCoords = targetObject.oCoords;

      // Horizontal
      if (Math.abs(tCoords.tl.y - oCoords.tl.y) < this.DPMM) {
        /*
                                  Top to top
        --------- <----> ---------        --------- <----> ---------
        |       |        |   T   |        |   T   |        |       |
        |   A   |        ---------   OR   ---------        |   A   |
        |       |                                          |       |
        ---------                                          ---------
        */
        targetObject.top = object.top;

        // Add snap line
        if (tCoords.tl.x < oCoords.tl.x) {
          // active object is to the left
          this._updateSnapLine([
            tCoords.tr.x, object.top,
            oCoords.tl.x, object.top,
          ]);
        } else {
          // active object is to the right
          this._updateSnapLine([
            oCoords.tr.x, object.top,
            tCoords.tl.x, object.top,
          ]);
        }
      } else if (Math.abs(tCoords.tl.y - oCoords.bl.y) < this.DPMM) {
        /*
                                Top to bottom
                         ---------        ---------
                         |   T   |        |   T   |
        --------- <----> ---------        --------- <----> ---------
        |       |                    OR                    |       |
        |   A   |                                          |   A   |
        |       |                                          |       |
        ---------                                          ---------

        */
        targetObject.top = object.top + object.getScaledHeight();

        // Add snap line
        if (tCoords.tl.x < oCoords.tl.x) {
          // active object is to the left
          this._updateSnapLine([
            tCoords.tr.x, targetObject.top,
            oCoords.bl.x, targetObject.top,
          ]);
        } else {
          // active object is to the right
          this._updateSnapLine([
            oCoords.tr.x, object.top + object.getScaledHeight(),
            tCoords.tl.x, object.top + object.getScaledHeight(),
          ]);
        }
      } else if (Math.abs(tCoords.bl.y - oCoords.bl.y) < this.DPMM) {
        /*
                              Bottom to bottom
        ---------                                          ---------
        |       |                                          |       |
        |   A   |        ---------   OR   ---------        |   A   |
        |       |        |   T   |        |   T   |        |       |
        --------- <----> ---------        --------- <----> ---------
        */
        targetObject.top = object.top + object.getScaledHeight() - targetObject.getScaledHeight();

        // Add snap line
        if (tCoords.tl.x < oCoords.tl.x) {
          // active object is to the left
          this._updateSnapLine([
            tCoords.tr.x, object.top + object.getScaledHeight(),
            oCoords.tl.x, object.top + object.getScaledHeight(),
          ]);
        } else {
          // active object is to the right
          this._updateSnapLine([
            oCoords.tr.x, object.top + object.getScaledHeight(),
            tCoords.tl.x, object.top + object.getScaledHeight(),
          ]);
        }
      } else if (Math.abs(tCoords.bl.y - oCoords.tl.y) < this.DPMM) {
        /*
                                Bottom to top
        ---------                                          ---------
        |       |                                          |       |
        |   A   |                                          |   A   |
        |       |                    OR                    |       |
        --------- <----> ---------        --------- <----> ---------
                         |   T   |        |   T   |
                         ---------        ---------
        */
        targetObject.top = object.top - targetObject.getScaledHeight();

        // Add snap line
        if (tCoords.tl.x < oCoords.tl.x) {
          // active object is to the left
          this._updateSnapLine([
            tCoords.br.x, targetObject.top + targetObject.getScaledHeight(),
            oCoords.tl.x, targetObject.top + targetObject.getScaledHeight(),
          ]);
        } else {
          // active object is to the right
          this._updateSnapLine([
            oCoords.tr.x, object.top,
            tCoords.bl.x, object.top,
          ]);
        }
      }

      // Vertical
      if (Math.abs(tCoords.tl.x - oCoords.tl.x) < this.DPMM) {
        /*
            Left to left
            ---------        ---------
            |   T   |        |       |
            ---------        |   A   |
                             |       |
            |                ---------
            |           OR
                             |
            ---------        |
            |       |
            |   A   |        ---------
            |       |        |   T   |
            ---------        ---------
        */
        targetObject.left = object.left;

        // Add snap line
        if (tCoords.tl.y < oCoords.tl.y) {
          // active object is above
          this._updateSnapLine([
            object.left, tCoords.tl.y,
            object.left, oCoords.bl.y,
          ]);
        } else {
          // active object is below
          this._updateSnapLine([
            object.left, oCoords.tl.y,
            object.left, tCoords.bl.y,
          ]);
        }
      } else if (Math.abs(tCoords.tl.x - oCoords.tr.x) < this.DPMM) {
        /*
            Left to right
            ---------                        ---------
            |   T   |                        |       |
            ---------                        |   A   |
                                             |       |
                    |                        ---------
                    |           OR
                                             |
                    ---------                |
                    |       |
                    |   A   |        ---------
                    |       |        |   T   |
                    ---------        ---------
        */
        targetObject.left = object.left + object.getScaledWidth();

        // Add snap line
        if (tCoords.tl.y < oCoords.tl.y) {
          // active object is above
          this._updateSnapLine([
            object.left + object.getScaledWidth(), tCoords.tl.y,
            object.left + object.getScaledWidth(), oCoords.bl.y,
          ]);
        } else {
          // active object is below
          this._updateSnapLine([
            object.left + object.getScaledWidth(), oCoords.tl.y,
            object.left + object.getScaledWidth(), tCoords.bl.y,
          ]);
        }
      } else if (Math.abs(tCoords.tr.x - oCoords.tr.x) < this.DPMM) {
        /*
            Right to right
            ---------                ---------
            |   T   |                |       |
            ---------                |   A   |
                                     |       |
                    |                ---------
                    |     OR
                                     |
            ---------                |
            |       |
            |   A   |        ---------
            |       |        |   T   |
            ---------        ---------
        */
        targetObject.left = object.left + object.getScaledWidth() - targetObject.getScaledWidth();

        // Add snap line
        if (tCoords.tl.y < oCoords.tl.y) {
          // active object is above
          this._updateSnapLine([
            object.left + object.getScaledWidth(), tCoords.tl.y,
            object.left + object.getScaledWidth(), oCoords.bl.y,
          ]);
        } else {
          // active object is below
          this._updateSnapLine([
            object.left + object.getScaledWidth(), oCoords.tl.y,
            object.left + object.getScaledWidth(), tCoords.bl.y,
          ]);
        }
      } else if (Math.abs(tCoords.tr.x - oCoords.tl.x) < this.DPMM) {
        /*
            Right to left
                    ---------        ---------
                    |   T   |        |       |
                    ---------        |   A   |
                                     |       |
                    |                ---------
                    |           OR
                                             |
            ---------                        |
            |       |
            |   A   |                        ---------
            |       |                        |   T   |
            ---------                        ---------
        */
        targetObject.left = object.left - targetObject.getScaledWidth();

        // Add snap line
        if (tCoords.tl.y < oCoords.tl.y) {
          // active object is above
          this._updateSnapLine([
            object.left, tCoords.tl.y,
            object.left, oCoords.bl.y,
          ]);
        } else {
          // active object is below
          this._updateSnapLine([
            object.left, oCoords.tl.y,
            object.left, tCoords.bl.y,
          ]);
        }
      }

      /*
                  By center (width)
          ---------           -------------
          |       |           |     T     |
          |   A   |           -------------
          |       |                 |
          ---------                 |
              |         OR          |
              |                 ---------
              |                 |       |
        -------------           |   A   |
        |     T     |           |       |
        -------------           ---------
      */
      const targetCenterX = tCoords.tl.x + targetObject.getScaledWidth() / 2;
      const objectCenterX = oCoords.tl.x + object.getScaledWidth() / 2;
      if (Math.abs(targetCenterX - objectCenterX) < this.DPMM) {
        // Center to center
        targetObject.left = object.left
          + object.getScaledWidth() / 2
          - targetObject.getScaledWidth() / 2;

        // Add snap line
        if (tCoords.tl.y < oCoords.tl.y) {
          // Active object is above
          this._updateSnapLine([
            object.left + object.getScaledWidth() / 2, tCoords.tl.y,
            object.left + object.getScaledWidth() / 2, oCoords.tl.y,
          ]);
        } else {
          // Active object is below
          this._updateSnapLine([
            object.left + object.getScaledWidth() / 2, oCoords.bl.y,
            object.left + object.getScaledWidth() / 2, tCoords.bl.y,
          ]);
        }
      }

      /*
                                By center (height)
          ---------                                          ---------
          |       |       ---------          ---------       |       |
          |   A   |  ---  |   T   |    OR    |   T   |  ---  |   A   |
          |       |       ---------          ---------       |       |
          ---------                                          ---------
      */
      const targetCenterY = tCoords.tl.y + targetObject.getScaledHeight() / 2;
      const objectCenterY = oCoords.tl.y + object.getScaledHeight() / 2;
      if (Math.abs(targetCenterY - objectCenterY) < this.DPMM) {
        // Center to center
        targetObject.top = object.top
          + object.getScaledHeight() / 2
          - targetObject.getScaledHeight() / 2;

        // Add snap line
        if (tCoords.tl.x < oCoords.tl.x) {
          // Active object is to the left
          this._updateSnapLine([
            tCoords.br.x, object.top + object.getScaledHeight() / 2,
            oCoords.tl.x, object.top + object.getScaledHeight() / 2,
          ]);
        } else {
          // Active object is to the right
          this._updateSnapLine([
            oCoords.tr.x, object.top + object.getScaledHeight() / 2,
            tCoords.bl.x, object.top + object.getScaledHeight() / 2,
          ]);
        }
      }
    });
  },

  _resetSnapLine: function () {
    if (this.snapLine) {
      this.canvas.remove(this.snapLine);
    }
  },

  _onShowGridClick: function (e) {
    if (e.target.checked) {
      this._renderGrid();
    } else {
      this._removeGrid();
    }
  },

  _addCustomFields: function () {
    const fields = this.parent.settings.allowed_fields || [];

    // Render widget
    const customFields = new CustomFieldsWidget(
      this, fields, this._addCustomFieldCallback.bind(this));
    customFields.appendTo(this.el.querySelector('.zld-custom-fields'));
  },

  _onCanvasTextChanged: (e) => {
    const object = e.target;

    if (object instanceof fabric.IText) {
      // Adjust text width
      const textLinesMaxWidth = object.textLines.reduce(
        (max, _, i) => Math.max(max, object.getLineWidth(i)), 0);
      object.set({ width: textLinesMaxWidth });
    }
  },

  commitChanges: function () {
    // Remove grid lines
    this._removeGrid();

    // Save canvas content only if record exists
    if (this.record.data.id) {
      this._setValue(
        JSON.stringify(this.canvas.toJSON(PROPERTIES_TO_SAVE)),
        { notify: false },
      );
    }
  },

  _onAddTextClick: function (e) {
    e.preventDefault();

    const text = e.target.dataset.value || 'Lorum ipsum';

    // Everything with data- attribute should be not editable
    // const editable = !e.target.dataset.value;

    this._addTextbox(text, true);
  },

  _onAddRectClick: function (e) {
    e.preventDefault();

    const rect = new fabric.Rect({
      id: this._generateUniqueID(),
      left: 100,
      top: 100,
      stroke: 'black',
      strokeWidth: 5,
      fill: null,
      width: 50,
      height: 50,
      snapAngle: 90,
      snapThreshold: 45,
      noScaleCache: false,
      strokeUniform: true,
    });

    // Do not allow to rotate rect
    rect.setControlsVisibility({ mtr: false });

    this.canvas.add(rect);
  },

  _onAddLineClick: function (e) {
    e.preventDefault();

    const line = new fabric.Line([100, 100, 200, 100], {
      id: this._generateUniqueID(),
      stroke: 'black',
      strokeWidth: 5,
      fill: null,
      noScaleCache: false,
      strokeUniform: true,
      snapAngle: 90,
      snapThreshold: 45,
    });

    this.canvas.add(line);
  },

  _addCustomFieldCallback: function (value) {
    this._addTextbox(`%%${value}%%`, true);
  },

  _addTextbox: function (text, editable) {
    const textbox = new fabric.Textbox(text, {
      id: this._generateUniqueID(),
      left: 50,
      top: 50,
      fontSize: 20,
      fontFamily: FONTS[0],
      padding: 2,
      editable: editable,
      snapAngle: 90,
      snapThreshold: 45,
      objectCaching: false,
      showTextBoxBorder: true,
      textboxBorderColor: '#dddddd',
    });

    this.canvas.add(textbox);
  },

  _generateUniqueID: () => (new Date()).getTime(),
});

fieldRegistry.add('zld_label_editor', LabelEditorField);
