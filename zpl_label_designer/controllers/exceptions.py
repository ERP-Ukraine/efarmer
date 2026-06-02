import werkzeug.exceptions as exceptions


class BadDatabaseName(exceptions.BadRequest):
    code = 400
    name = 'Database name is missed or invalid'

    def __str__(self) -> str:
        return f'{self.name}'


class MissedRequiredParameters(exceptions.NotFound):
    code = 400
    name = 'Required parameters missed'

    def __str__(self) -> str:
        return f'{self.name}: {self.description}'


class InvalidAPIKey(exceptions.Unauthorized):
    code = 401
    name = 'Invalid or missed API key'

    def __str__(self) -> str:
        return f'{self.name}'


class MissedModule(exceptions.NotFound):
    code = 404
    name = 'ZPL Label Designer module is not installed or need to be upgraded'

    def __str__(self) -> str:
        return f'{self.name}'


class ModelNotAllowed(exceptions.BadRequest):
    code = 400
    name = 'Model is not allowed. Please add it in ZPL Label Designer / Settings'

    def __str__(self) -> str:
        return f'{self.name}'


class PreviewError(exceptions.BadRequest):
    code = 400
    name = 'Error while generating preview'

    def __str__(self) -> str:
        return f'{self.name}: {self.description}'


class CreateLabelError(exceptions.BadRequest):
    code = 400
    name = 'Error while creating label'

    def __str__(self) -> str:
        return f'{self.name}: {self.description}'


class LabelNotFound(exceptions.NotFound):
    code = 404
    name = 'Label not found'

    def __str__(self) -> str:
        return f'{self.name}'


class UpdateLabelError(exceptions.BadRequest):
    code = 400
    name = 'Error while updating label'

    def __str__(self) -> str:
        return f'{self.name}: {self.description}'


class DeleteLabelError(exceptions.BadRequest):
    code = 400
    name = 'Error while deleting label'

    def __str__(self) -> str:
        return f'{self.name}: {self.description}'
