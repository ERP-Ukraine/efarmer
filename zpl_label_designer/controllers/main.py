from odoo import fields, release
from odoo.http import Controller, route, request

from .exceptions import (
    CreateLabelError, DeleteLabelError, ModelNotAllowed, PreviewError, UpdateLabelError
)
from .utils import add_env, catchall, required, validate


ALLOWED_FIELDS = [
    fields.Char, fields.Text,
    fields.Integer, fields.Float,
    fields.Boolean, fields.Many2one,
    fields.Selection, fields.Datetime,
    # Experimental
    fields.One2many, fields.Many2many,
]
FIELDS_TO_IGNORE = ['create_uid', 'write_uid']
CREATE_LABEL_REQUIRED_FIELDS = [
    'name', 'model', 'qweb_xml', 'label_fields',
    'width', 'height', 'dpi', 'orientation', 'designer_label_id',
]
UPDATE_LABEL_REQUIRED_FIELDS = [
    'name', 'model', 'qweb_xml', 'label_fields',
    'width', 'height', 'dpi', 'orientation', 'designer_label_id',
]

RESPONSE_HEADERS = {
    'Content-Type': 'application/json',
}


class ZLDController(Controller):
    @route('/zld/<string:db>/ping', type='json', auth='none', csrf=False, methods=['POST'])
    @catchall
    @add_env
    @validate
    def ping(self, db):
        """
        Ping the server to check if it is alive and has installed the module
        """
        module_version = request.env['ir.module.module'].search(
            [['name', '=', 'zpl_label_designer']]).latest_version
        odoo_version = release.major_version

        return {
            'data': {
                'odoo_version': odoo_version,
                'zld_version': module_version,
            }
        }

    @route('/zld/<string:db>/models', type='json', auth='none', csrf=False, methods=['POST'])
    @catchall
    @add_env
    @validate
    def get_allowed_models(self, db, *args, **kwargs):
        """
        Returns allowed models to use in the designer.
        """
        allowed_models = [
            {'id': model.id, 'model': model.model, 'name': model.name}
            for model in request.env.company.zld_allowed_models.sudo()]

        return {
            'data': allowed_models,
        }

    @route('/zld/<string:db>/fields', type='json', auth='none', csrf=False, methods=['POST'])
    @catchall
    @add_env
    @validate
    @required('model')
    def get_allowed_fields(self, db, model, *args, **kwargs):
        """
        Returns list of fields to use in label design (sorted by label)
        like [{name: ..., label: ..., type: ..., comodel: ...}, ...]

        :param model: optional str: 'res.company', 'res.partner', ...
        """
        # We do not check for allowed models here because we need to have possibility
        # to get fields for any model to use in label design

        fields_ = []

        for field_name, field in request.env[model]._fields.items():
            if field_name in FIELDS_TO_IGNORE or field_name.startswith('_'):
                continue

            if any([isinstance(field, FieldType) for FieldType in ALLOWED_FIELDS]):
                fields_.append({
                    'name': field_name,
                    'label': field.string,
                    'type': type(field).type,
                    'comodel': getattr(field, 'comodel_name', False),
                })

        fields_.sort(key=lambda d: d['label'])

        return {
            'data': fields_,
        }

    @route('/zld/<string:db>/preview', type='json', auth='none', csrf=False, methods=['POST'])
    @catchall
    @add_env
    @validate
    @required('model', 'fields')
    def get_preview(self, db, model, fields, *args, **kwargs):
        """
        Returns preview with demo data.
        """
        # Check that model is in allowed models
        allowed_model_names = [m.model for m in request.env.company.zld_allowed_models.sudo()]
        if model not in allowed_model_names:
            raise ModelNotAllowed()

        try:
            data_for_preview = request.env['zld.label'].get_preview_data(model, fields)
        except Exception as e:
            raise PreviewError(str(e))

        return {
            'data': data_for_preview,
        }

    @route('/zld/<string:db>/labels', type='json', auth='none', csrf=False, methods=['POST'])
    @catchall
    @add_env
    @validate
    @required(*CREATE_LABEL_REQUIRED_FIELDS)
    def create_label(self, db, *args, **kwargs):
        """
        Return preview with demo data.
        """
        data = {field: kwargs.get(field) for field in CREATE_LABEL_REQUIRED_FIELDS}

        model = data['model']

        # Check that model is in allowed models
        allowed_model_names = [m.model for m in request.env.company.zld_allowed_models.sudo()]
        if model not in allowed_model_names:
            raise ModelNotAllowed()

        try:
            label_id = request.env['zld.label'].create_label(data)
        except Exception as e:
            raise CreateLabelError(str(e))

        return {
            'data': {'label_id': label_id}
        }

    @route('/zld/<string:db>/labels/<int:label_id>', type='json', auth='none',csrf=False,  methods=['POST'])  # NOQA
    @catchall
    @add_env
    @validate
    @required(*UPDATE_LABEL_REQUIRED_FIELDS)
    def update_label(self, db, label_id, *args, **kwargs):
        """
        Update label and return label ID.
        """
        data = {field: kwargs.get(field) for field in UPDATE_LABEL_REQUIRED_FIELDS}

        try:
            label_id = request.env['zld.label'].update_label(label_id, data)
        except Exception as e:
            raise UpdateLabelError(str(e))

        return {
            'data': {'label_id': label_id},
        }

    @route('/zld/<string:db>/labels/<int:label_id>/delete', type='json', auth='none', csrf=False, methods=['POST'])  # NOQA
    @catchall
    @add_env
    @validate
    def delete_label(self, db, label_id, *args, **kwargs):
        """
        Delete label and return label ID.
        """
        try:
            request.env['zld.label'].delete_label(label_id)
        except Exception as e:
            raise DeleteLabelError(str(e))

        return {
            'data': {},
        }
