# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


# ShopifyPaymentsTransactionType — Admin GraphQL 2026-04.
# https://shopify.dev/docs/api/admin-graphql/2026-04/enums/ShopifyPaymentsTransactionType
# Odoo stores Char (enum keeps growing); ``to_odoo_format`` → member name (snake/lower).
TRANSACTION_TYPE_MAP = {
    'ACH_BANK_FAILURE_DEBIT_FEE': (
        'Ach Bank Failure Debit Fee',
        'The ach_bank_failure_debit_fee transaction type.',
    ),
    'ACH_BANK_FAILURE_DEBIT_REVERSAL_FEE': (
        'Ach Bank Failure Debit Reversal Fee',
        'The ach_bank_failure_debit_reversal_fee transaction type.',
    ),
    'ADJUSTMENT': (
        'Adjustment',
        'The adjustment transaction type.',
    ),
    'ADS_PUBLISHER_CREDIT': (
        'Ads Publisher Credit',
        'The ads_publisher_credit transaction type.',
    ),
    'ADS_PUBLISHER_CREDIT_REVERSAL': (
        'Ads Publisher Credit Reversal',
        'The ads_publisher_credit_reversal transaction type.',
    ),
    'ADVANCE': (
        'Advance',
        'The advance transaction type.',
    ),
    'ADVANCE_FUNDING': (
        'Advance Funding',
        'The advance_funding transaction type.',
    ),
    'ANOMALY_CREDIT': (
        'Anomaly Credit',
        'The anomaly_credit transaction type.',
    ),
    'ANOMALY_CREDIT_REVERSAL': (
        'Anomaly Credit Reversal',
        'The anomaly_credit_reversal transaction type.',
    ),
    'ANOMALY_DEBIT': (
        'Anomaly Debit',
        'The anomaly_debit transaction type.',
    ),
    'ANOMALY_DEBIT_REVERSAL': (
        'Anomaly Debit Reversal',
        'The anomaly_debit_reversal transaction type.',
    ),
    'APPLICATION_FEE_REFUND': (
        'Application Fee Refund',
        'The application_fee_refund transaction type.',
    ),
    'BALANCE_TRANSFER_INBOUND': (
        'Balance Transfer Inbound',
        'The balance_transfer_inbound transaction type.',
    ),
    'BALANCE_TRANSFER_OUTBOUND': (
        'Balance Transfer Outbound',
        'The balance_transfer_outbound transaction type.',
    ),
    'BILLING_DEBIT': (
        'Billing Debit',
        'The billing_debit transaction type.',
    ),
    'BILLING_DEBIT_REVERSAL': (
        'Billing Debit Reversal',
        'The billing_debit_reversal transaction type.',
    ),
    'CHANNEL_CREDIT': (
        'Channel Credit',
        'The channel_credit transaction type.',
    ),
    'CHANNEL_CREDIT_REVERSAL': (
        'Channel Credit Reversal',
        'The channel_credit_reversal transaction type.',
    ),
    'CHANNEL_PROMOTION_CREDIT': (
        'Channel Promotion Credit',
        'The channel_promotion_credit transaction type.',
    ),
    'CHANNEL_PROMOTION_CREDIT_REVERSAL': (
        'Channel Promotion Credit Reversal',
        'The channel_promotion_credit_reversal transaction type.',
    ),
    'CHANNEL_TRANSFER_CREDIT': (
        'Channel Transfer Credit',
        'The channel_transfer_credit transaction type.',
    ),
    'CHANNEL_TRANSFER_CREDIT_REVERSAL': (
        'Channel Transfer Credit Reversal',
        'The channel_transfer_credit_reversal transaction type.',
    ),
    'CHANNEL_TRANSFER_DEBIT': (
        'Channel Transfer Debit',
        'The channel_transfer_debit transaction type.',
    ),
    'CHANNEL_TRANSFER_DEBIT_REVERSAL': (
        'Channel Transfer Debit Reversal',
        'The channel_transfer_debit_reversal transaction type.',
    ),
    'CHARGE': (
        'Charge',
        'The charge transaction type.',
    ),
    'CHARGE_ADJUSTMENT': (
        'Charge Adjustment',
        'The charge_adjustment transaction type.',
    ),
    'CHARGEBACK_FEE': (
        'Chargeback Fee',
        'The chargeback_fee transaction type.',
    ),
    'CHARGEBACK_FEE_REFUND': (
        'Chargeback Fee Refund',
        'The chargeback_fee_refund transaction type.',
    ),
    'CHARGEBACK_HOLD': (
        'Chargeback Hold',
        'The chargeback_hold transaction type.',
    ),
    'CHARGEBACK_HOLD_RELEASE': (
        'Chargeback Hold Release',
        'The chargeback_hold_release transaction type.',
    ),
    'CHARGEBACK_PROTECTION_CREDIT': (
        'Chargeback Protection Credit',
        'The chargeback_protection_credit transaction type.',
    ),
    'CHARGEBACK_PROTECTION_CREDIT_REVERSAL': (
        'Chargeback Protection Credit Reversal',
        'The chargeback_protection_credit_reversal transaction type.',
    ),
    'CHARGEBACK_PROTECTION_DEBIT': (
        'Chargeback Protection Debit',
        'The chargeback_protection_debit transaction type.',
    ),
    'CHARGEBACK_PROTECTION_DEBIT_REVERSAL': (
        'Chargeback Protection Debit Reversal',
        'The chargeback_protection_debit_reversal transaction type.',
    ),
    'COLLECTIONS_CREDIT': (
        'Collections Credit',
        'The collections_credit transaction type.',
    ),
    'COLLECTIONS_CREDIT_REVERSAL': (
        'Collections Credit Reversal',
        'The collections_credit_reversal transaction type.',
    ),
    'CUSTOMS_DUTY': (
        'Customs Duty',
        'The customs_duty transaction type.',
    ),
    'CUSTOMS_DUTY_ADJUSTMENT': (
        'Customs Duty Adjustment',
        'The customs_duty_adjustment transaction type.',
    ),
    'DISPUTE_REVERSAL': (
        'Dispute Reversal',
        'The dispute_reversal transaction type.',
    ),
    'DISPUTE_WITHDRAWAL': (
        'Dispute Withdrawal',
        'The dispute_withdrawal transaction type.',
    ),
    'IMPORT_TAX': (
        'Import Tax',
        'The import_tax transaction type.',
    ),
    'IMPORT_TAX_ADJUSTMENT': (
        'Import Tax Adjustment',
        'The import_tax_adjustment transaction type.',
    ),
    'IMPORT_TAX_REFUND': (
        'Import Tax Refund',
        'The import_tax_refund transaction type.',
    ),
    'LENDING_CAPITAL_REFUND': (
        'Lending Capital Refund',
        'The lending_capital_refund transaction type.',
    ),
    'LENDING_CAPITAL_REFUND_REVERSAL': (
        'Lending Capital Refund Reversal',
        'The lending_capital_refund_reversal transaction type.',
    ),
    'LENDING_CAPITAL_REMITTANCE': (
        'Lending Capital Remittance',
        'The lending_capital_remittance transaction type.',
    ),
    'LENDING_CAPITAL_REMITTANCE_REVERSAL': (
        'Lending Capital Remittance Reversal',
        'The lending_capital_remittance_reversal transaction type.',
    ),
    'LENDING_CREDIT': (
        'Lending Credit',
        'The lending_credit transaction type.',
    ),
    'LENDING_CREDIT_REFUND': (
        'Lending Credit Refund',
        'The lending_credit_refund transaction type.',
    ),
    'LENDING_CREDIT_REFUND_REVERSAL': (
        'Lending Credit Refund Reversal',
        'The lending_credit_refund_reversal transaction type.',
    ),
    'LENDING_CREDIT_REMITTANCE': (
        'Lending Credit Remittance',
        'The lending_credit_remittance transaction type.',
    ),
    'LENDING_CREDIT_REMITTANCE_REVERSAL': (
        'Lending Credit Remittance Reversal',
        'The lending_credit_remittance_reversal transaction type.',
    ),
    'LENDING_CREDIT_REVERSAL': (
        'Lending Credit Reversal',
        'The lending_credit_reversal transaction type.',
    ),
    'LENDING_DEBIT': (
        'Lending Debit',
        'The lending_debit transaction type.',
    ),
    'LENDING_DEBIT_REVERSAL': (
        'Lending Debit Reversal',
        'The lending_debit_reversal transaction type.',
    ),
    'MARKETPLACE_FEE_CREDIT': (
        'Marketplace Fee Credit',
        'The marketplace_fee_credit transaction type.',
    ),
    'MARKETPLACE_FEE_CREDIT_REVERSAL': (
        'Marketplace Fee Credit Reversal',
        'The marketplace_fee_credit_reversal transaction type.',
    ),
    'MARKETS_PRO_CREDIT': (
        'Markets Pro Credit',
        'The markets_pro_credit transaction type.',
    ),
    'MERCHANT_GOODWILL_CREDIT': (
        'Merchant Goodwill Credit',
        'The merchant_goodwill_credit transaction type.',
    ),
    'MERCHANT_GOODWILL_CREDIT_REVERSAL': (
        'Merchant Goodwill Credit Reversal',
        'The merchant_goodwill_credit_reversal transaction type.',
    ),
    'MERCHANT_TO_MERCHANT_CREDIT': (
        'Merchant To Merchant Credit',
        'The merchant_to_merchant_credit transaction type.',
    ),
    'MERCHANT_TO_MERCHANT_CREDIT_REVERSAL': (
        'Merchant To Merchant Credit Reversal',
        'The merchant_to_merchant_credit_reversal transaction type.',
    ),
    'MERCHANT_TO_MERCHANT_DEBIT': (
        'Merchant To Merchant Debit',
        'The merchant_to_merchant_debit transaction type.',
    ),
    'MERCHANT_TO_MERCHANT_DEBIT_REVERSAL': (
        'Merchant To Merchant Debit Reversal',
        'The merchant_to_merchant_debit_reversal transaction type.',
    ),
    'PROMOTION_CREDIT': (
        'Promotion Credit',
        'The promotion_credit transaction type.',
    ),
    'PROMOTION_CREDIT_REVERSAL': (
        'Promotion Credit Reversal',
        'The promotion_credit_reversal transaction type.',
    ),
    'REFERRAL_FEE': (
        'Referral Fee',
        'The referral_fee transaction type.',
    ),
    'REFERRAL_FEE_TAX': (
        'Referral Fee Tax',
        'The referral_fee_tax transaction type.',
    ),
    'REFUND': (
        'Refund',
        'The refund transaction type.',
    ),
    'REFUND_ADJUSTMENT': (
        'Refund Adjustment',
        'The refund_adjustment transaction type.',
    ),
    'REFUND_FAILURE': (
        'Refund Failure',
        'The refund_failure transaction type.',
    ),
    'RESERVED_FUNDS': (
        'Reserved Funds',
        'The reserved_funds transaction type.',
    ),
    'RESERVED_FUNDS_REVERSAL': (
        'Reserved Funds Reversal',
        'The reserved_funds_reversal transaction type.',
    ),
    'RESERVED_FUNDS_WITHDRAWAL': (
        'Reserved Funds Withdrawal',
        'The reserved_funds_withdrawal transaction type.',
    ),
    'RISK_REVERSAL': (
        'Risk Reversal',
        'The risk_reversal transaction type.',
    ),
    'RISK_WITHDRAWAL': (
        'Risk Withdrawal',
        'The risk_withdrawal transaction type.',
    ),
    'SELLER_PROTECTION_CREDIT': (
        'Seller Protection Credit',
        'The seller_protection_credit transaction type.',
    ),
    'SELLER_PROTECTION_CREDIT_REVERSAL': (
        'Seller Protection Credit Reversal',
        'The seller_protection_credit_reversal transaction type.',
    ),
    'SHIPPING_LABEL': (
        'Shipping Label',
        'The shipping_label transaction type.',
    ),
    'SHIPPING_LABEL_ADJUSTMENT': (
        'Shipping Label Adjustment',
        'The shipping_label_adjustment transaction type.',
    ),
    'SHIPPING_LABEL_ADJUSTMENT_BASE': (
        'Shipping Label Adjustment Base',
        'The shipping_label_adjustment_base transaction type.',
    ),
    'SHIPPING_LABEL_ADJUSTMENT_SURCHARGE': (
        'Shipping Label Adjustment Surcharge',
        'The shipping_label_adjustment_surcharge transaction type.',
    ),
    'SHIPPING_OTHER_CARRIER_CHARGE_ADJUSTMENT': (
        'Shipping Other Carrier Charge Adjustment',
        'The shipping_other_carrier_charge_adjustment transaction type.',
    ),
    'SHIPPING_RETURN_TO_ORIGIN_ADJUSTMENT': (
        'Shipping Return To Origin Adjustment',
        'The shipping_return_to_origin_adjustment transaction type.',
    ),
    'SHOP_CASH_BILLING_DEBIT': (
        'Shop Cash Billing Debit',
        'The shop_cash_billing_debit transaction type.',
    ),
    'SHOP_CASH_BILLING_DEBIT_REVERSAL': (
        'Shop Cash Billing Debit Reversal',
        'The shop_cash_billing_debit_reversal transaction type.',
    ),
    'SHOP_CASH_CAMPAIGN_BILLING_CREDIT': (
        'Shop Cash Campaign Billing Credit',
        'The shop_cash_campaign_billing_credit transaction type.',
    ),
    'SHOP_CASH_CAMPAIGN_BILLING_CREDIT_REVERSAL': (
        'Shop Cash Campaign Billing Credit Reversal',
        'The shop_cash_campaign_billing_credit_reversal transaction type.',
    ),
    'SHOP_CASH_CAMPAIGN_BILLING_DEBIT': (
        'Shop Cash Campaign Billing Debit',
        'The shop_cash_campaign_billing_debit transaction type.',
    ),
    'SHOP_CASH_CAMPAIGN_BILLING_DEBIT_REVERSAL': (
        'Shop Cash Campaign Billing Debit Reversal',
        'The shop_cash_campaign_billing_debit_reversal transaction type.',
    ),
    'SHOP_CASH_CREDIT': (
        'Shop Cash Credit',
        'The shop_cash_credit transaction type.',
    ),
    'SHOP_CASH_CREDIT_REVERSAL': (
        'Shop Cash Credit Reversal',
        'The shop_cash_credit_reversal transaction type.',
    ),
    'SHOP_CASH_REFUND_DEBIT': (
        'Shop Cash Refund Debit',
        'The shop_cash_refund_debit transaction type.',
    ),
    'SHOP_CASH_REFUND_DEBIT_REVERSAL': (
        'Shop Cash Refund Debit Reversal',
        'The shop_cash_refund_debit_reversal transaction type.',
    ),
    'SHOPIFY_COLLECTIVE_CREDIT': (
        'Shopify Collective Credit',
        'The shopify_collective_credit transaction type.',
    ),
    'SHOPIFY_COLLECTIVE_CREDIT_REVERSAL': (
        'Shopify Collective Credit Reversal',
        'The shopify_collective_credit_reversal transaction type.',
    ),
    'SHOPIFY_COLLECTIVE_DEBIT': (
        'Shopify Collective Debit',
        'The shopify_collective_debit transaction type.',
    ),
    'SHOPIFY_COLLECTIVE_DEBIT_REVERSAL': (
        'Shopify Collective Debit Reversal',
        'The shopify_collective_debit_reversal transaction type.',
    ),
    'SHOPIFY_SOURCE_CREDIT': (
        'Shopify Source Credit',
        'The shopify_source_credit transaction type.',
    ),
    'SHOPIFY_SOURCE_CREDIT_REVERSAL': (
        'Shopify Source Credit Reversal',
        'The shopify_source_credit_reversal transaction type.',
    ),
    'SHOPIFY_SOURCE_DEBIT': (
        'Shopify Source Debit',
        'The shopify_source_debit transaction type.',
    ),
    'SHOPIFY_SOURCE_DEBIT_REVERSAL': (
        'Shopify Source Debit Reversal',
        'The shopify_source_debit_reversal transaction type.',
    ),
    'STRIPE_FEE': (
        'Stripe Fee',
        'The stripe_fee transaction type.',
    ),
    'TAX_ADJUSTMENT_CREDIT': (
        'Tax Adjustment Credit',
        'The tax_adjustment_credit transaction type.',
    ),
    'TAX_ADJUSTMENT_CREDIT_REVERSAL': (
        'Tax Adjustment Credit Reversal',
        'The tax_adjustment_credit_reversal transaction type.',
    ),
    'TAX_ADJUSTMENT_DEBIT': (
        'Tax Adjustment Debit',
        'The tax_adjustment_debit transaction type.',
    ),
    'TAX_ADJUSTMENT_DEBIT_REVERSAL': (
        'Tax Adjustment Debit Reversal',
        'The tax_adjustment_debit_reversal transaction type.',
    ),
    'TRANSFER': (
        'Transfer',
        'The transfer transaction type.',
    ),
    'TRANSFER_CANCEL': (
        'Transfer Cancel',
        'The transfer_cancel transaction type.',
    ),
    'TRANSFER_FAILURE': (
        'Transfer Failure',
        'The transfer_failure transaction type.',
    ),
    'TRANSFER_REFUND': (
        'Transfer Refund',
        'The transfer_refund transaction type.',
    ),
    'VAT_REFUND_CREDIT': (
        'Vat Refund Credit',
        'The vat_refund_credit transaction type.',
    ),
    'VAT_REFUND_CREDIT_REVERSAL': (
        'Vat Refund Credit Reversal',
        'The vat_refund_credit_reversal transaction type.',
    ),
}


class ShopifyPaymentsTransactionType(StatusAbstract):
    """ShopifyPaymentsTransactionType — GraphQL value uppercase, Odoo via ``to_odoo_format``."""

    ach_bank_failure_debit_fee = 'ACH_BANK_FAILURE_DEBIT_FEE'
    ach_bank_failure_debit_reversal_fee = 'ACH_BANK_FAILURE_DEBIT_REVERSAL_FEE'
    adjustment = 'ADJUSTMENT'
    ads_publisher_credit = 'ADS_PUBLISHER_CREDIT'
    ads_publisher_credit_reversal = 'ADS_PUBLISHER_CREDIT_REVERSAL'
    advance = 'ADVANCE'
    advance_funding = 'ADVANCE_FUNDING'
    anomaly_credit = 'ANOMALY_CREDIT'
    anomaly_credit_reversal = 'ANOMALY_CREDIT_REVERSAL'
    anomaly_debit = 'ANOMALY_DEBIT'
    anomaly_debit_reversal = 'ANOMALY_DEBIT_REVERSAL'
    application_fee_refund = 'APPLICATION_FEE_REFUND'
    balance_transfer_inbound = 'BALANCE_TRANSFER_INBOUND'
    balance_transfer_outbound = 'BALANCE_TRANSFER_OUTBOUND'
    billing_debit = 'BILLING_DEBIT'
    billing_debit_reversal = 'BILLING_DEBIT_REVERSAL'
    channel_credit = 'CHANNEL_CREDIT'
    channel_credit_reversal = 'CHANNEL_CREDIT_REVERSAL'
    channel_promotion_credit = 'CHANNEL_PROMOTION_CREDIT'
    channel_promotion_credit_reversal = 'CHANNEL_PROMOTION_CREDIT_REVERSAL'
    channel_transfer_credit = 'CHANNEL_TRANSFER_CREDIT'
    channel_transfer_credit_reversal = 'CHANNEL_TRANSFER_CREDIT_REVERSAL'
    channel_transfer_debit = 'CHANNEL_TRANSFER_DEBIT'
    channel_transfer_debit_reversal = 'CHANNEL_TRANSFER_DEBIT_REVERSAL'
    charge = 'CHARGE'
    charge_adjustment = 'CHARGE_ADJUSTMENT'
    chargeback_fee = 'CHARGEBACK_FEE'
    chargeback_fee_refund = 'CHARGEBACK_FEE_REFUND'
    chargeback_hold = 'CHARGEBACK_HOLD'
    chargeback_hold_release = 'CHARGEBACK_HOLD_RELEASE'
    chargeback_protection_credit = 'CHARGEBACK_PROTECTION_CREDIT'
    chargeback_protection_credit_reversal = 'CHARGEBACK_PROTECTION_CREDIT_REVERSAL'
    chargeback_protection_debit = 'CHARGEBACK_PROTECTION_DEBIT'
    chargeback_protection_debit_reversal = 'CHARGEBACK_PROTECTION_DEBIT_REVERSAL'
    collections_credit = 'COLLECTIONS_CREDIT'
    collections_credit_reversal = 'COLLECTIONS_CREDIT_REVERSAL'
    customs_duty = 'CUSTOMS_DUTY'
    customs_duty_adjustment = 'CUSTOMS_DUTY_ADJUSTMENT'
    dispute_reversal = 'DISPUTE_REVERSAL'
    dispute_withdrawal = 'DISPUTE_WITHDRAWAL'
    import_tax = 'IMPORT_TAX'
    import_tax_adjustment = 'IMPORT_TAX_ADJUSTMENT'
    import_tax_refund = 'IMPORT_TAX_REFUND'
    lending_capital_refund = 'LENDING_CAPITAL_REFUND'
    lending_capital_refund_reversal = 'LENDING_CAPITAL_REFUND_REVERSAL'
    lending_capital_remittance = 'LENDING_CAPITAL_REMITTANCE'
    lending_capital_remittance_reversal = 'LENDING_CAPITAL_REMITTANCE_REVERSAL'
    lending_credit = 'LENDING_CREDIT'
    lending_credit_refund = 'LENDING_CREDIT_REFUND'
    lending_credit_refund_reversal = 'LENDING_CREDIT_REFUND_REVERSAL'
    lending_credit_remittance = 'LENDING_CREDIT_REMITTANCE'
    lending_credit_remittance_reversal = 'LENDING_CREDIT_REMITTANCE_REVERSAL'
    lending_credit_reversal = 'LENDING_CREDIT_REVERSAL'
    lending_debit = 'LENDING_DEBIT'
    lending_debit_reversal = 'LENDING_DEBIT_REVERSAL'
    marketplace_fee_credit = 'MARKETPLACE_FEE_CREDIT'
    marketplace_fee_credit_reversal = 'MARKETPLACE_FEE_CREDIT_REVERSAL'
    markets_pro_credit = 'MARKETS_PRO_CREDIT'
    merchant_goodwill_credit = 'MERCHANT_GOODWILL_CREDIT'
    merchant_goodwill_credit_reversal = 'MERCHANT_GOODWILL_CREDIT_REVERSAL'
    merchant_to_merchant_credit = 'MERCHANT_TO_MERCHANT_CREDIT'
    merchant_to_merchant_credit_reversal = 'MERCHANT_TO_MERCHANT_CREDIT_REVERSAL'
    merchant_to_merchant_debit = 'MERCHANT_TO_MERCHANT_DEBIT'
    merchant_to_merchant_debit_reversal = 'MERCHANT_TO_MERCHANT_DEBIT_REVERSAL'
    promotion_credit = 'PROMOTION_CREDIT'
    promotion_credit_reversal = 'PROMOTION_CREDIT_REVERSAL'
    referral_fee = 'REFERRAL_FEE'
    referral_fee_tax = 'REFERRAL_FEE_TAX'
    refund = 'REFUND'
    refund_adjustment = 'REFUND_ADJUSTMENT'
    refund_failure = 'REFUND_FAILURE'
    reserved_funds = 'RESERVED_FUNDS'
    reserved_funds_reversal = 'RESERVED_FUNDS_REVERSAL'
    reserved_funds_withdrawal = 'RESERVED_FUNDS_WITHDRAWAL'
    risk_reversal = 'RISK_REVERSAL'
    risk_withdrawal = 'RISK_WITHDRAWAL'
    seller_protection_credit = 'SELLER_PROTECTION_CREDIT'
    seller_protection_credit_reversal = 'SELLER_PROTECTION_CREDIT_REVERSAL'
    shipping_label = 'SHIPPING_LABEL'
    shipping_label_adjustment = 'SHIPPING_LABEL_ADJUSTMENT'
    shipping_label_adjustment_base = 'SHIPPING_LABEL_ADJUSTMENT_BASE'
    shipping_label_adjustment_surcharge = 'SHIPPING_LABEL_ADJUSTMENT_SURCHARGE'
    shipping_other_carrier_charge_adjustment = 'SHIPPING_OTHER_CARRIER_CHARGE_ADJUSTMENT'
    shipping_return_to_origin_adjustment = 'SHIPPING_RETURN_TO_ORIGIN_ADJUSTMENT'
    shop_cash_billing_debit = 'SHOP_CASH_BILLING_DEBIT'
    shop_cash_billing_debit_reversal = 'SHOP_CASH_BILLING_DEBIT_REVERSAL'
    shop_cash_campaign_billing_credit = 'SHOP_CASH_CAMPAIGN_BILLING_CREDIT'
    shop_cash_campaign_billing_credit_reversal = 'SHOP_CASH_CAMPAIGN_BILLING_CREDIT_REVERSAL'
    shop_cash_campaign_billing_debit = 'SHOP_CASH_CAMPAIGN_BILLING_DEBIT'
    shop_cash_campaign_billing_debit_reversal = 'SHOP_CASH_CAMPAIGN_BILLING_DEBIT_REVERSAL'
    shop_cash_credit = 'SHOP_CASH_CREDIT'
    shop_cash_credit_reversal = 'SHOP_CASH_CREDIT_REVERSAL'
    shop_cash_refund_debit = 'SHOP_CASH_REFUND_DEBIT'
    shop_cash_refund_debit_reversal = 'SHOP_CASH_REFUND_DEBIT_REVERSAL'
    shopify_collective_credit = 'SHOPIFY_COLLECTIVE_CREDIT'
    shopify_collective_credit_reversal = 'SHOPIFY_COLLECTIVE_CREDIT_REVERSAL'
    shopify_collective_debit = 'SHOPIFY_COLLECTIVE_DEBIT'
    shopify_collective_debit_reversal = 'SHOPIFY_COLLECTIVE_DEBIT_REVERSAL'
    shopify_source_credit = 'SHOPIFY_SOURCE_CREDIT'
    shopify_source_credit_reversal = 'SHOPIFY_SOURCE_CREDIT_REVERSAL'
    shopify_source_debit = 'SHOPIFY_SOURCE_DEBIT'
    shopify_source_debit_reversal = 'SHOPIFY_SOURCE_DEBIT_REVERSAL'
    stripe_fee = 'STRIPE_FEE'
    tax_adjustment_credit = 'TAX_ADJUSTMENT_CREDIT'
    tax_adjustment_credit_reversal = 'TAX_ADJUSTMENT_CREDIT_REVERSAL'
    tax_adjustment_debit = 'TAX_ADJUSTMENT_DEBIT'
    tax_adjustment_debit_reversal = 'TAX_ADJUSTMENT_DEBIT_REVERSAL'
    transfer = 'TRANSFER'
    transfer_cancel = 'TRANSFER_CANCEL'
    transfer_failure = 'TRANSFER_FAILURE'
    transfer_refund = 'TRANSFER_REFUND'
    vat_refund_credit = 'VAT_REFUND_CREDIT'
    vat_refund_credit_reversal = 'VAT_REFUND_CREDIT_REVERSAL'

    @property
    def mapping(self):
        return TRANSACTION_TYPE_MAP

    @classmethod
    def _missing_(cls, value):
        """Forward-compat: Shopify adds members; Char storage uses the lowercased name."""
        if isinstance(value, str) and value:
            obj = object.__new__(cls)
            obj._name_ = value.lower()
            obj._value_ = value
            return obj
        return None
