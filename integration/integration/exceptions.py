# See LICENSE file for full copyright and licensing details.


class NotMappedFromExternal(Exception):

    def __init__(self, msg, model_name=None, code=None, integration=None):
        if model_name and code:
            msg = '%s(code=%s, integration=%s) \n%s' % (model_name, code, str(integration.id), msg)

        super(NotMappedFromExternal, self).__init__(msg)


class NotMappedFromExternalMulti(Exception):
    def __init__(self, msg, model_name=None, records=None, integration=None):
        if model_name and records:
            msg = (
                '%s(code=%s, integration=%s) \n%s' % (model_name, records, str(integration.id), msg)
            )

        super(NotMappedFromExternalMulti, self).__init__(msg)


class NotMappedToExternal(Exception):

    def __init__(self, msg, model_name=None, obj_id=None, integration=None):
        if model_name and obj_id:
            msg = '%s(id=%s, integration=%s) \n%s' % (model_name, obj_id, str(integration.id), msg)

        super(NotMappedToExternal, self).__init__(msg)


class NoReferenceFieldDefined(Exception):

    def __init__(self, msg, object_name=None):
        super(NoReferenceFieldDefined, self).__init__(msg)
        self.object_name = object_name


class ApiImportError(Exception):

    def __init__(self, msg):
        super(ApiImportError, self).__init__(msg)


class ApiExportError(Exception):

    def __init__(self, msg):
        super(ApiExportError, self).__init__(msg)


class NoExternal(Exception):

    def __init__(self, msg, model_name=None, code=None, integration=None):
        if model_name and code:
            msg = '%s(code=%s, integration=%s) \n%s' % (model_name, code, str(integration.id), msg)

        super(NoExternal, self).__init__(msg)
