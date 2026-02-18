# See LICENSE file for full copyright and licensing details.

from odoo.tools import _, LazyTranslate
from odoo.exceptions import UserError, ValidationError

from inspect import stack
from logging import getLogger
from requests.exceptions import SSLError, ConnectionError as RequestsConnectionError
from typing import Type, NamedTuple, Optional, List


_logger = getLogger(__name__)
_lt = LazyTranslate(__name__)


class NotMappedFromExternal(Exception):

    def __init__(self, msg, model_name=None, code=None, integration=None):
        if model_name and code:
            msg = '%s → %s(code=%s, integration=%s) \n%s' % (integration.name, model_name, code, integration.id, msg)

        super(NotMappedFromExternal, self).__init__(msg)


class NotMappedToExternal(Exception):

    def __init__(self, msg, model_name=None, obj_id=None, integration=None):
        if model_name and obj_id and integration:
            msg = (
                f'Export error for model "{model_name}" with ID "{obj_id}" in {integration.name} '
                f'integration (ID: {integration.id}).\n'
                f'Details: {msg}\n\n'
                f'Suggested action: The corresponding external record does not exist. This usually means '
                f'the Odoo entity (e.g., product) was not exported to the e-commerce system.\n'
                f'Please try the following steps:\n'
                f'  1. Manually export the problematic entity from Odoo to the e-commerce system, or\n'
                f'  2. If there is an export job in the queue, please wait until the export job is completed.\n\n'
                f'If the issue persists or the export fails, please contact our support '
                f'team: https://support.ventor.tech/'
            )
        else:
            msg = (
                f'Export error: {msg}\n\n'
                f'Suggested action: The corresponding external record does not exist. Please manually export '
                f'the Odoo entity to '
                f'the e-commerce system or wait for the export job to complete. '
                f'If the issue persists, please contact our support team: https://support.ventor.tech/'
            )

        super(NotMappedToExternal, self).__init__(msg)


class NoReferenceFieldDefined(Exception):

    def __init__(self, msg, object_name=None):
        super(NoReferenceFieldDefined, self).__init__(msg)
        self.object_name = object_name


class ApiImportError(Exception):

    pass


class ApiExportError(Exception):

    pass


class NoExternal(Exception):

    def __init__(self, msg, model_name=None, code=None, integration=None):
        if model_name and code and integration:
            msg = (
                f'External record not found for model "{model_name}" with code "{code}" in '
                f'integration ID {integration.id}.\n'
                f'Details: {msg}\n\n'
                f'Suggested action: Please ensure the relevant objects are imported from the e-commerce system.\n'
                f'Steps to resolve:\n'
                f'  1. Check the e-commerce system to confirm that the record with code "{code}" exists.\n'
                f'  2. If the record exists, make sure it is correctly imported into Odoo via the import process.\n'
                f'  3. If the record does not exist, ensure it is created in the e-commerce system and '
                f'then import it into Odoo.\n\n'
                f'If the issue persists, please contact our support team: https://support.ventor.tech/'
            )
        else:
            msg = (
                f'External record not found: {msg}\n\n'
                f'Suggested action: Please ensure the relevant objects are imported from the e-commerce system.\n'
                f'Steps to resolve:\n'
                f'  1. Confirm the external record exists in the e-commerce system.\n'
                f'  2. Import the record into Odoo using the import process.\n\n'
                f'If the issue persists, please contact our support team: https://support.ventor.tech/'
            )

        super(NoExternal, self).__init__(msg)


class UndefinedExternalProduct(Exception):

    pass


class NotFoundExternalProduct(Exception):

    pass


class MultipleExternalRecordsFound(Exception):

    def __init__(self, msg, model_name=None, code=None, integration=None, duplicates=None):
        if model_name and code and integration:
            duplicate_info = ', '.join(str(dup.id) for dup in duplicates) if duplicates else 'unknown'
            msg = (
                f'Multiple external records found for model "{model_name}" with code "{code}" '
                f'in {integration.name} integration (ID: {integration.id}).\n'
                f'Details: {msg}\n'
                f'Duplicate record IDs: {duplicate_info}\n\n'
                f'Suggested action: Please remove duplicates in the external records.\n'
                f'Steps to resolve:\n'
                f'  1. Go to the external records for "{model_name}" model and search for records with code "{code}".\n'
                f'  2. Identify and remove the duplicated records to ensure only one unique record exists.\n'
                f'  3. Once the duplicates are resolved, restart any failed jobs or retry '
                f'the action you were attempting.\n\n'
                f'If the issue persists, please contact our support team: https://support.ventor.tech/'
            )
        else:
            msg = (
                f'Multiple external records found: {msg}\n\n'
                f'Suggested action: Please remove duplicates in the external records.\n'
                f'Steps to resolve:\n'
                f'  1. Search for the relevant records in the external system and resolve duplicates.\n'
                f'  2. Once the duplicates are resolved, restart any failed jobs or retry '
                f'the action you were attempting.\n\n'
                f'If the issue persists, please contact our support team: https://support.ventor.tech/'
            )

        super(MultipleExternalRecordsFound, self).__init__(msg)


class IntegrationNotImplementedError(NotImplementedError):

    def __init__(self, msg: str = ''):
        method_name = stack()[1].function
        # Format string first, then translate to avoid translation context issues
        formatted_msg = (
            'Method %(method_name)s must be implemented by each connector. '
            'Additional information: %(msg)s\n\n'
            'This is a technical issue that cannot be fixed through configuration and requires '
            'investigation by our developers. '
            'If you encounter this error, please contact our support team: https://support.ventor.tech/'
        ) % {'method_name': method_name, 'msg': msg}
        msg = str(_lt(formatted_msg))

        super(IntegrationNotImplementedError, self).__init__(formatted_msg)


class JsonMissedKey(Exception):

    pass


class ResourceConflict(Exception):  # HTTP error 409
    CODE = 409

    def __init__(self, message: str):
        super().__init__(f'{self.CODE}: {message}')


class TooManyRequestsError(Exception):  # HTTP error 429
    CODE = 429

    def __init__(self, message: str):
        super().__init__(f'{self.CODE}: {message}')


class ServerError(Exception):  # HTTP error 500-599

    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f'{code}: {message}')


class ErrorInfo(NamedTuple):

    error_type: Type[Exception] = UserError
    format_method: Optional[str] = None  # noqa: E701
    format_method_params: Optional[List] = None  # noqa: E701


class ErrorStore:
    """Utility class for generating standardized error messages.
    This class cannot be instantiated - use its static methods directly.

    TODO: new format E1xx, E2xx, etc.
    For example:
    E0xx: Invalid usage of ErrorStore
    E1xx: Import errors
    E2xx: Export errors
    E3xx: Mapping errors
    .
    .
    .
    E9xx: Technical errors"""

    UserError = UserError
    ValidationError = ValidationError

    ApiImportError = ApiImportError
    ApiExportError = ApiExportError

    IntegrationNotImplementedError = IntegrationNotImplementedError
    JsonMissedKey = JsonMissedKey

    NotMappedToExternal = NotMappedToExternal
    NotMappedFromExternal = NotMappedFromExternal

    UndefinedExternalProduct = UndefinedExternalProduct
    NotFoundExternalProduct = NotFoundExternalProduct

    SSLError = SSLError
    RequestsConnectionError = RequestsConnectionError
    ResourceConflict = ResourceConflict
    ServerError = ServerError
    TooManyRequestsError = TooManyRequestsError

    NoReferenceFieldDefined = NoReferenceFieldDefined

    _error_codes = {
        'E000': ErrorInfo(),  # Common error code for raise non-standart integration errors
        'E001': ErrorInfo(),  # Unknown error code provided to ErrorStore.raise_error
        'E002': ErrorInfo(
            error_type=UserError,
            format_method='format_wrong_error_store_params',
        ),
        'E101': ErrorInfo(
            format_method='format_circular_dependency_related_products',
            format_method_params=[
                'parent_product',
                'optional_products',
                'integration_name=None',
            ],
        ),
        'E102': ErrorInfo(
            format_method='format_related_product_not_exported',
            format_method_params=[
                'parent_product',
                'optional_products',
                'integration_name=None',
            ],
        ),
        'E103': ErrorInfo(
            format_method='format_no_external',
            format_method_params=[
                'msg',
                'model_name=None',
                'code=None',
                'integration=None',
            ],
        ),
        'E104': ErrorInfo(
            format_method='format_multiple_external_records_found',
            format_method_params=[
                'msg',
                'model_name=None',
                'code=None',
                'integration=None',
                'duplicates=None',
            ],
        ),
        'E105': ErrorInfo(
            error_type=IntegrationNotImplementedError,
            format_method='format_integration_not_implemented',
            format_method_params=[
                'method_name',
                'msg=None',
            ],
        ),
        'E106': ErrorInfo(
            error_type=NotMappedFromExternal,
            format_method='format_not_mapped_from_external',
            format_method_params=[
                'msg',
                'model_name=None',
                'code=None',
                'integration=None',
            ],
        ),
        'E107': ErrorInfo(
            error_type=NotMappedToExternal,
            format_method='format_not_mapped_to_external',
            format_method_params=[
                'msg',
                'model_name=None',
                'obj_id=None',
                'integration=None',
            ],
        ),
        'E108': ErrorInfo(
            error_type=ApiImportError,
        ),
        'E109': ErrorInfo(
            error_type=UndefinedExternalProduct,
            format_method='format_undefined_external_product',
            format_method_params=[
                'integration_name',
                'product_name',
                'product_reference',
            ],
        ),
        'E110': ErrorInfo(
            error_type=NotFoundExternalProduct,
            format_method='format_not_found_external_product',
            format_method_params=[
                'integration_name',
                'product_id',
                'variant_id',
                'product_name',
                'product_reference',
            ],
        )
    }

    def __new__(cls):
        raise TypeError(_("%(cls_name)s cannot be instantiated. Use static methods directly.") % {
            'cls_name': cls.__name__,
        })

    @classmethod
    def raise_error(
        cls,
        err_type: Type[Exception] = None,
        err_code: str = 'E000',
        err_msg: str = '',
        support_contact: bool = True,
        **kwargs,
    ):
        """
        Method to raise an error with a given error code or message.
        """
        if not err_code == 'E000' and err_msg:
            _logger.warning(
                '\n\tBoth error code and error message provided to ErrorStore.raise_error.'
                '\n\tIn that case err_msg has higher priority than format_message.\n'
            )

        if not err_type:
            err_type = cls._error_codes.get(err_code).error_type

        if err_code and err_code != 'E000':
            if not err_msg:
                err_msg = cls.format_message(err_code, **kwargs)
            else:
                err_msg = _('\n\nError %(err_code)s:\n%(err_msg)s\n') % {
                    'err_code': err_code,
                    'err_msg': err_msg,
                }

        if support_contact:
            err_msg += cls.format_support_contact_string()

        raise err_type(err_msg)

    @classmethod
    def format_message(cls, err_code: str, support_contact: bool = False, **kwargs):
        error_info = cls._error_codes.get(err_code, None)
        if error_info.format_method:
            return _(
                '\n\nError %(err_code)s:\n'
            ) % {'err_code': err_code} \
                + getattr(cls, error_info.format_method)(**kwargs) \
                + (cls.format_support_contact_string() if support_contact else '')

        cls.raise_error(
            err_code='E001',
            err_msg=_('Unknown error code provided to ErrorStore.raise_error: %(err_code)s.') % {
                'err_code': err_code,
            },
            support_contact=True,
        )

    @staticmethod
    def format_support_contact_string():
        return str(_lt('\n\nIf you need assistance, please contact our support team: https://support.ventor.tech/'))

    @staticmethod
    def format_not_mapped_from_external(msg, model_name=None, code=None, integration=None):
        if model_name and code:
            return '%(integration)s → %(model)s(code=%(code)s, integration=%(integration_id)s) \n%(msg)s' % {
                'integration': integration.name,
                'model': model_name,
                'code': code,
                'integration_id': integration.id,
                'msg': msg,
            }
        return msg

    @staticmethod
    def format_not_mapped_to_external(msg, model_name=None, obj_id=None, integration=None):
        if model_name and obj_id and integration:
            return _(
                'Export error for model "%(model)s" with ID "%(obj_id)s" in %(integration_name)s '
                'integration (ID: %(integration_id)s).\n'
                'Details: %(msg)s\n\n'
                'Suggested action: The corresponding external record does not exist. This usually means '
                'the Odoo entity (e.g., product) was not exported to the e-commerce system.\n'
                'Please try the following steps:\n'
                '  1. Manually export the problematic entity from Odoo to the e-commerce system, or\n'
                '  2. If there is an export job in the queue, please wait until the export job is completed.'
            ) % {
                'model': model_name,
                'obj_id': obj_id,
                'integration_name': integration.name,
                'integration_id': integration.id,
                'msg': msg,
            }
        return _(
            'Export error: %(msg)s\n\n'
            'Suggested action: The corresponding external record does not exist. Please manually export '
            'the Odoo entity to '
            'the e-commerce system or wait for the export job to complete. '
        ) % {'msg': msg}

    @staticmethod
    def format_no_external(msg, model_name=None, code=None, integration=None):
        if model_name and code and integration:
            return _(
                'External record not found for model "%(model)s" with code "%(code)s" in '
                'integration ID %(integration_id)s.\n'
                'Details: %(msg)s\n\n'
                'Suggested action: Please ensure the relevant objects are imported from the e-commerce system.\n'
                'Steps to resolve:\n'
                '  1. Check the e-commerce system to confirm that the record with code "%(code)s" exists.\n'
                '  2. If the record exists, make sure it is correctly imported into Odoo via the import process.\n'
                '  3. If the record does not exist, ensure it is created in the e-commerce system and '
                'then import it into Odoo.'
            ) % {
                'model': model_name,
                'code': code,
                'integration_id': integration.id,
                'msg': msg,
            }
        return _(
            'External record not found: %(msg)s\n\n'
            'Suggested action: Please ensure the relevant objects are imported from the e-commerce system.\n'
            'Steps to resolve:\n'
            '  1. Confirm the external record exists in the e-commerce system.\n'
            '  2. Import the record into Odoo using the import process.'
        ) % {'msg': msg}

    @staticmethod
    def format_multiple_external_records_found(
        msg, model_name=None, code=None, integration=None, duplicates=None,
    ):
        if model_name and code and integration:
            duplicate_info = ', '.join(str(dup.id) for dup in duplicates) if duplicates else 'unknown'
            return _(
                'Multiple external records found for model "%(model)s" with code "%(code)s" '
                'in %(integration_name)s integration (ID: %(integration_id)s).\n'
                'Details: %(msg)s\n'
                'Duplicate record IDs: %(duplicate_info)s\n\n'
                'Suggested action: Please remove duplicates in the external records.\n'
                'Steps to resolve:\n'
                '  1. Go to the external records for "%(model)s" model and search for records with code "%(code)s".\n'
                '  2. Identify and remove the duplicated records to ensure only one unique record exists.\n'
                '  3. Once the duplicates are resolved, restart any failed jobs or retry '
                'the action you were attempting.'
            ) % {
                'model': model_name,
                'code': code,
                'integration_name': integration.name,
                'integration_id': integration.id,
                'msg': msg,
                'duplicate_info': duplicate_info,
            }
        return _(
            'Multiple external records found: %(msg)s\n\n'
            'Suggested action: Please remove duplicates in the external records.\n'
            'Steps to resolve:\n'
            '  1. Search for the relevant records in the external system and resolve duplicates.\n'
            '  2. Once the duplicates are resolved, restart any failed jobs or retry '
            'the action you were attempting.'
        ) % {'msg': msg}

    @staticmethod
    def format_integration_not_implemented(method_name, msg=''):
        return _(
            'Method %(method_name)s must be implemented by each connector. '
            'Additional information: %(msg)s\n\n'
            'This is a technical issue that cannot be fixed through configuration and requires '
            'investigation by our developers.'
        ) % {
            'method_name': method_name,
            'msg': msg,
        }

    @staticmethod
    def format_circular_dependency_related_products(parent_product, optional_products, integration_name=None):
        if not parent_product or not optional_products:
            raise ValueError(_(
                'Invalid arguments provided to ErrorStore.format_circular_dependency_related_products (E101).\n'
                'Both parent_product and optional_products must be provided.'
            ))

        platform = integration_name or 'the e-commerce platform'
        return (_(
            'Circular dependency detected between product "%(parent)s '
            '(Internal Reference: %(parent_internal_reference)s)" and next related products:\n'
            '%(optional_products)s\n\n'
            'Example: Product "%(parent)s" is linked as a related product to "%(optional)s", '
            'and vice versa. This creates an export loop.\n\n'
            'To resolve this issue follow these steps:\n'
            '1. Open Product Field Mappings and disable "Related Products" synchronization.\n'
            '2. Export all related products manually to %(platform)s.\n'
            '3. Then export "%(parent)s" again.\n'
            '4. Finally, re-enable "Related Products" synchronization and export again.\n\n'
            'This ensures all products are linked correctly without recursion.'
        ) % {
            'optional_products': '\n'.join([
                f'\t- Product: {product.name} (Internal Reference: {product.default_code})'
                for product in optional_products
            ]),
            'parent': parent_product.name,
            'parent_internal_reference': parent_product.default_code,
            'optional': optional_products[0].name,
            'platform': platform,
        })

    @staticmethod
    def format_related_product_not_exported(parent_product, optional_products, integration_name=None):
        if not parent_product or not optional_products:
            raise ValueError(_(
                'Invalid arguments provided to ErrorStore.format_related_product_not_exported.\n'
                'Both parent_product and optional_products must be provided.'
            ))

        platform = integration_name or 'the e-commerce platform'
        return (_(
            'There were problems exporting this product: '
            '"%(parent)s (Internal Reference: %(parent_internal_reference)s)" to %(platform)s.\n\n'
            'Next related products were not exported:\n'
            '%(optional_products)s\n\n'
            'Options to resolve this issue:\n'
            '1. Export all related products(see above) manually to %(platform)s and run "%(parent)s" export again.\n'
            '2. Open Product Field Mappings and disable "Related Products" synchronization '
            'and run "%(parent)s" export again to export only parent product.'
        ) % {
            'optional_products': '\n'.join([
                f'\t- Product: {product.name} (Internal Reference: {product.default_code})'
                for product in optional_products
            ]),
            'parent': parent_product.name,
            'parent_internal_reference': parent_product.default_code or '',
            'platform': platform,
        })

    @staticmethod
    def format_undefined_external_product(integration_name, product_name, product_reference):
        return _(
            '%s: The product "%s" (%s) cannot be imported because it does not have an identifier in the e-commerce system.\n\n'  # noqa: E501
            'This can happen in the following cases:\n'
            '- The order contains a custom or manually added item that is not linked to a real product\n'
            '- The product was removed from the store and automatically unlinked from the order\n'
            '- The product was created or modified by a customization and does not have a valid identifier\n'
            'Please review the order and product data in the e-commerce system and try again.'

        ) % (integration_name, product_name, product_reference)

    @staticmethod
    def format_not_found_external_product(
        integration_name,
        product_id,
        variant_id,
        product_name,
        product_reference,
    ):
        return _(
            '%s: The product "%s" (%s) with (ID=%s, Variant-ID=%s) could not be found in the e-commerce system. '
            'It may have been deleted, archived, or is no longer available. '
            'Please verify that the product and its variants still exist in your store.'
        ) % (integration_name, product_name, product_reference, product_id, variant_id)
