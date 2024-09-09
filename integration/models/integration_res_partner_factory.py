# See LICENSE file for full copyright and licensing details.

from typing import Dict, List, Tuple

from odoo import api, fields, models, registry, _

from ..exceptions import ApiImportError, NotMappedFromExternal
from ..tools import freeze_arguments


class IntegrationResPartnerFactory(models.TransientModel):
    _name = 'integration.res.partner.factory'
    _description = 'Integration Res Partner Factory'

    integration_id = fields.Many2one(
        string='e-Commerce Integration',
        comodel_name='sale.integration',
        required=True,
    )

    proxy_ids = fields.One2many(
        string='Proxies',
        comodel_name='integration.res.partner.proxy',
        inverse_name='factory_id',
        help=(
            'Proxies associated with this factory.'
        ),
    )

    is_initial_import = fields.Boolean(
        string='Initial Import',
        help='Flag indicating whether this is the initial import.',
    )

    @property
    def customer_proxy(self):
        return self.proxy_ids.filtered(lambda r: r.type == 'customer')

    @property
    def shipping_proxy(self):
        return self.proxy_ids.filtered(lambda r: r.type == 'shipping_address')

    @property
    def billing_proxy(self):
        return self.proxy_ids.filtered(lambda r: r.type == 'billing_address')

    @property
    def other_proxies(self):
        return self.proxy_ids.filtered(lambda r: r.type == 'other_address')

    @property
    def customer_id(self):
        return self.customer_proxy.partner_id

    @api.model
    @freeze_arguments('customer_data', 'billing_data', 'shipping_data', 'addresses_data')
    def create_factory(
            self, integration_id: int, customer_data: Dict, *,
            billing_data: Dict = None, shipping_data: Dict = None,
            addresses_data: List = None, is_initial_import: bool = False,
    ) -> models.Model:
        """
        Creates a new factory and associated proxies.
        Args:
            integration_id : ID of the integration.
            customer_data: Customer data for creating customer proxy.
            billing_data: Billing data for creating billing proxy.
            shipping_data: Shipping data for creating shipping proxy.
            addresses_data: List of additional addresses data for creating other proxies.
            is_initial_import: Flag indicating if this is an initial import.
        Returns:
            models.Model: The created factory instance.
        """
        Proxy = self.env['integration.res.partner.proxy']
        factory = self.create({
            'integration_id': integration_id,
            'is_initial_import': is_initial_import,
        })

        # Helper function to create proxy
        def create_proxy_from_data(proxy_type, data):
            if data:
                Proxy.create_proxy(proxy_type, factory.id, data)

        # Update customer data with billing data if available
        customer_data = self._update_customer_data(customer_data, billing_data, shipping_data)

        # Create proxies
        # Use billing_data if customer_data is empty to create a partner for guest orders
        create_proxy_from_data('customer', customer_data or billing_data)
        create_proxy_from_data('billing_address', billing_data)
        create_proxy_from_data('shipping_address', shipping_data)

        if addresses_data:
            for address in addresses_data:
                create_proxy_from_data('other_address', address)

        return factory

    def _update_customer_data(self, customer_data, billing_data, shipping_data):
        """
            Update customer data with billing data if available.
            Args:
                customer_data: Customer data.
                billing_data: Billing data.
                shipping_data: Shipping data. Shipping data is not used in this method. For overriding this method.
        """
        if customer_data and billing_data:
            customer_data['person_id_number'] = billing_data.get('person_id_number', '')

            # Update company-related fields from billing data if available
            if 'company_name' in billing_data:
                customer_data['company_name'] = billing_data.get('company_name', '')
                customer_data['company_reg_number'] = billing_data.get('company_reg_number', '')
                # Get the country or country_code from the billing data to validation VAT for the company
                customer_data['country'] = billing_data.get('country', '')
                customer_data['country_code'] = billing_data.get('country_code', '')

        return customer_data

    @api.model
    def get_partner_and_addresses(self) -> Tuple[models.Model, Dict]:
        """
        Create or retrieve customer and contact addresses.
        Returns:
            A tuple containing the customer partner record and a dictionary containing shipping,
            billing, and other addresses.
        """
        self.validate_data()

        customer = shipping = billing = self.integration_id.default_customer

        if self.customer_proxy:
            if self.integration_id.use_manual_customer_mapping:
                customer = self.customer_proxy.get_customer()
            else:
                customer = self.customer_proxy.get_or_create_partner()

            self.customer_proxy._post_update_partner(customer)

        if self.shipping_proxy:
            shipping = self.shipping_proxy._get_or_create_address()

        if self.billing_proxy:
            billing = self.billing_proxy._get_or_create_address()

        other_addresses = []
        if self.other_proxies:
            for other_address in self.other_proxies:
                other_addresses.append(other_address._get_or_create_address())

        return customer, {'shipping': shipping, 'billing': billing, 'other': other_addresses}

    def validate_data(self):
        """
        Validate the data before processing it.
        This method performs basic validation on the data provided.
        If the import is flagged as an initial import, additional validation specific to initial
        imports is performed. Otherwise, validation for sales orders is executed.
        """
        if self.is_initial_import:
            self._validate_for_initial_import()
        else:
            self._validate_for_sales_orders()

    def _validate_for_initial_import(self):
        """
        Validate data specific to initial imports.
        This method checks if the customer has an external ID, raising an error if it's missing.
        """
        if not self.customer_proxy.external_id:
            raise ApiImportError('Customer external ID is missing')

        mapping = self.env['res.partner'].get_mapping(
            self.integration_id,
            self.customer_proxy.external_id,
        )

        # Handle manual partner mapping enabled case.
        if self.integration_id.use_manual_customer_mapping and not mapping.partner_id:
            # Create a new open mapping for the current external ID
            self.customer_proxy._create_or_update_mapping(with_new_cursor=True)

            # Raise an NotMappedFromExternal with a message indicating the failure in
            # mapping customers.
            raise NotMappedFromExternal(_(
                '\nThe "Enable Manual Customer Mapping" setting is enabled on the integration.\n'
                'Partner "%s" not mapped for external ID %s\n'
                'Please map partners in the "Mappings → Contacts" menu.') % (
                self.customer_proxy.person_name, self.customer_proxy.external_id,
                ), 'integration.res.partner.mapping', self.customer_proxy.external_id,
                self.integration_id)

    def _validate_for_sales_orders(self) -> bool:
        """
        Validate data for sales orders.
        This method ensures that the customer, shipping, and billing information is available.
        If any of them is missing and the default customer setting is not enabled, it raises an
        error.
        """
        partner = self.customer_proxy.get_customer(False)

        if not all([self.customer_proxy, self.shipping_proxy, self.billing_proxy]):
            if not self.integration_id.default_customer:
                raise ApiImportError(_('\n\n' 'Order we are trying to import into Odoo do not have '
                                       'Customer, Invoice Address or/and Delivery Address defined. '
                                       'But in Odoo it is not possible to create Sales Order '
                                       'without this information. Please, go to menu "e-Commerce '
                                       'Integration → select your sales integration" and on "Sales '
                                       'Order Defaults" tab select setting "Default Customer". '
                                       'And requeue job. Selected partner will be used instead of '
                                       'missing information, so sales order will not be blocked '
                                       'from creation'))

        # Handle manual partner mapping enabled case.
        if self.integration_id.use_manual_customer_mapping and not partner:
            # If customer is not found in the order - skip sending notifications and apply
            # "Default customer" to the order
            if not self.customer_proxy.external_id:
                return False

            # Notify about the failure in mapping customers
            self._notify_about_missed_customer_mapping()

            # Create a new open mapping for the current external ID
            self.customer_proxy._create_or_update_mapping(with_new_cursor=True)

            # Raise an NotMappedFromExternal with a message indicating the failure in
            # mapping customers.
            raise NotMappedFromExternal(_(
                '\nPartner "%s" not found for external ID %s; notification emails have been sent.\n'
                'Please map partners in the "Mappings → Contacts" menu.') % (
                self.customer_proxy.person_name, self.customer_proxy.external_id,
                ), 'integration.res.partner.mapping', self.customer_proxy.external_id,
                self.integration_id)

        return True

    def _notify_about_missed_customer_mapping(self):
        """
        Sends notification emails about failed customer mapping using a separate database cursor.
        This ensures that the email is sent reliably, even if the main transaction is rolled back.
        """
        db_registry = registry(self.env.cr.dbname)
        with db_registry.cursor() as new_cr:
            new_env = api.Environment(new_cr, self.env.uid, {})
            mail_template = new_env.ref('integration.mail_template_notify_failed_mapping')

            menu_id = new_env.ref('integration.menu_contacts_mapping').id
            model_name = 'integration_res_partner_mapping'
            url_menu = f'/web#view_type=list&model=integration.{model_name}&view_id=integration.' \
                       f'{model_name}_view_tree&menu_id={menu_id}'

            ctx = dict(self.env.context)
            ctx.update({
                'person_name': self.customer_proxy.person_name,
                'email': self.customer_proxy.email,
                'url_menu': url_menu,
            })

            for email in self.integration_id.emails_for_failed_mapping_notifications.split(','):
                email_values = {
                    'email_from': self.env.user.email_formatted,
                    'email_to': email,
                }

                mail_template.with_context(ctx).send_mail(
                    self.integration_id.id,
                    email_values=email_values,
                    force_send=True,
                )

        return True
