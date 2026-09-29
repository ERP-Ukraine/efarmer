#  See LICENSE file for full copyright and licensing details.
# flake8: noqa
# pylint: skip-file


class GraphQLTemplate:
    """GraphQl query templates"""

    MODEL_SCHEMA = """
        {
            __type(name: "%s") {
                name
                description
                kind
                fields {
                    name
                    description
                    args {
                        name
                        description
                        type {
                            name
                            kind
                            ofType {
                                name
                                kind
                            }
                        }
                    }
                    type {
                        name
                        kind
                        ofType {
                            name
                            kind
                        }
                    }
                }
            }
        }
    """

    BASE_SCHEMA = """
        query getRecord($id: ID!) {
            node(id: $id) {
                ... on %s {
                    %s
                }
            }
        }
    """

    USER_ERRORS_BODY_1 = """
        field
        message
    """

    USER_ERRORS_BODY_2 = """
        code
        field
        message
    """

    SHOP_LOCALE_BODY = """
        name
        locale
        primary
        published
    """

    MAILING_ADDRESS_BODY = """
        id
        firstName
        lastName
        phone
        address1
        address2
        city
        company
        country
        countryCodeV2
        provinceCode
        zip
    """

    SHOP_ADDRESS_BODY = """
        country
        countryCodeV2
        city
        zip
        provinceCode
    """

    SHOP_BODY = """
        id
        url
        name
        email
        myshopifyDomain
        weightUnit
        ianaTimezone
        timezoneOffset
        taxesIncluded
        taxShipping
        currencyCode
        shopAddress {
            %s
        }
    """ % SHOP_ADDRESS_BODY

    MEDIA_BODY = """
        id
        alt
        status
        mediaContentType
        preview {
            image {
                id
                url
            }
        }
    """

    FILE_BODY = """
        id
        preview {
            image {
                id
                url
            }
        }
        fileStatus
        fileErrors {
            code
            details
            message
        }
    """

    COLLECTION_BODY = """
        id
        title
        handle
        description
    """

    TRANSLATION_BODY = """
        key
        value
        locale
        outdated
    """

    TRANSLATABLE_CONTENT_BODY = """
        key
        value
        locale
        digest
    """

    TRANSLATABLE_RESOURCE_SAMPLE_BODY_MIN_1 = """
        resourceId
        translations(locale: "%%s") {
            %s
        }
        translatableContent {
            %s
        }
    """ % (TRANSLATION_BODY, TRANSLATABLE_CONTENT_BODY)

    TRANSLATABLE_RESOURCE_SAMPLE_BODY_MIN_2 = """
        resourceId
        translatableContent {
            %s
        }
    """ % TRANSLATABLE_CONTENT_BODY

    TRANSLATABLE_RESOURCE_SAMPLE_BODY_1 = """
        %%s: translatableResource(resourceId: "%%s") {
            %s
            nestedTranslatableResources(first: 20) {
                nodes {
                    %s
                }
            }
        }
    """ % (TRANSLATABLE_RESOURCE_SAMPLE_BODY_MIN_1, TRANSLATABLE_RESOURCE_SAMPLE_BODY_MIN_1)

    TRANSLATABLE_RESOURCE_SAMPLE_BODY_2 = """
        translatableResource(resourceId: "%%s") {
            %s
            nestedTranslatableResources(first: 20) {
                nodes {
                    %s
                }
            }
        }
    """ % (TRANSLATABLE_RESOURCE_SAMPLE_BODY_MIN_2, TRANSLATABLE_RESOURCE_SAMPLE_BODY_MIN_2)

    NESTED_TRANSLATABLE_RESOURCE_SAMPLE_BODY = """
        %%s: nestedTranslatableResources(first: 20) {
            resourceId
            translations(locale: "%%s") {
                %s
            }
            translatableContent {
                %s
            }
        }
    """ % (TRANSLATION_BODY, TRANSLATABLE_CONTENT_BODY)

    PRODUCT_OPTION_VALUE_BODY = """
        id
        name
        hasVariants
    """

    PRODUCT_OPTION_BODY = """
        id
        name
        position
        optionValues {
            %s
        }
    """ % PRODUCT_OPTION_VALUE_BODY

    INVENTORY_ITEM_BODY = """
        id
        tracked
        harmonizedSystemCode
        countryCodeOfOrigin
        unitCost {
            amount
            currencyCode
        }
        measurement {
            weight {
                unit
                value
            }
        }
        inventoryLevels(first: 25) {
            nodes {
                id
                location {
                    id
                }
                quantities(names: "available") {
                    id
                    name
                    quantity
                }
            }
        }
    """

    # Only combined listings/bundles share one inventory item across variants, so this
    # is appended just where that lookup is needed (INVENTORY_LEVEL_BODY, for stock sync),
    # not on every query that embeds INVENTORY_ITEM_BODY. A result page this full is the
    # signal InventoryItem.get_variants() uses to detect truncation -- keep this in sync
    # with that check.
    INVENTORY_ITEM_VARIANTS_PAGE_SIZE = 50

    INVENTORY_ITEM_VARIANTS_BODY = """
        variants(first: %d) {
            nodes {
                id
                product {
                    id
                }
            }
        }
    """ % INVENTORY_ITEM_VARIANTS_PAGE_SIZE

    METAFIELD_DEFINITION_BODY = """
        id
        name
        key
        namespace
        type {
            name
        }
    """

    METAFIELD_BODY = """
        id
        key
        value
        namespace
        type
        ownerType
    """

    TAXONOMY_CATEGORY_BODY = """
        id
        name
        fullName
        level
        parentId
        ancestorIds
        isArchived
    """

    TAXONOMY_BODY = """
        categories(first: 250) {
            nodes {
                %s
            }
        }
    """ % TAXONOMY_CATEGORY_BODY

    TAXONOMY_GET_CATEGORIES_BODY = """
        categories(first: 250) {
            pageInfo {
                endCursor
                hasNextPage
            }
            edges {
                node {
                    %s
                }
            }
        }
    """ % TAXONOMY_CATEGORY_BODY

    INVENTORY_LEVEL_BODY = """
        id
        location {
            id
        }
        quantities(names: "available") {
            id
            quantity
            updatedAt
        }
        item {
            %s
            %s
        }
    """ % (INVENTORY_ITEM_BODY, INVENTORY_ITEM_VARIANTS_BODY)

    LOCATION_BODY = """
        id
        name
        isActive
        address {
            formatted
        }
    """

    LOCATION_GET_STOCK_LEVELS_BODY = """
        id
        inventoryLevels(first: 250) {
            nodes {
                %s
            }
            pageInfo {
                hasNextPage
                endCursor
            }
        }
    """ % INVENTORY_LEVEL_BODY

    PRICE_LIST_PRICE_BODY = """
        variant {
            id
        }
        originType
        price {
            amount
            currencyCode
        }
        compareAtPrice {
            amount
            currencyCode
        }
    """

    PRICELIST_PARENT_BODY = """
        adjustment {
            type
            value
        }
        settings {
            compareAtMode
        }
    """
    PRICELIST_BODY = """
        id
        name
        currency
        parent {
            %s
        }
    """ % PRICELIST_PARENT_BODY

    CURRENCY_SETTING_BODY = """
        currencyCode
        currencyName
        enabled
    """

    MARKET_REGION_COUNTRY_BODY = """
        code
    """

    MARKET_REGION_SUBDIVISION_BODY = """
        code
        country {
            code
            name
        }
    """

    MARKET_BODY = """
        id
        name
        type
        currencySettings {
            baseCurrency {
                %s
            }
        }
        conditions {
            regionsCondition {
                regions(first: 250) {
                    nodes {
                        __typename
                        id
                        name
                        ... on MarketRegionCountry {
                            %s
                        }
                        ... on MarketRegionSubdivision {
                            %s
                        }
                    }
                }
            }
        }
    """ % (CURRENCY_SETTING_BODY, MARKET_REGION_COUNTRY_BODY, MARKET_REGION_SUBDIVISION_BODY)

    CATALOG_BODY = """
        id
        title
        status
        priceList {
            %s
        }
        publication {
            id
        }

    """ % PRICELIST_BODY

    MARKET_CATALOG_BODY = """
        %s
        ... on MarketCatalog {
            markets(first: 12) {
                nodes {
                    %s
                }
            }
        }
    """ % (CATALOG_BODY, MARKET_BODY)

    COMPANY_LOCATION_CATALOG_BODY = """
        %s
        ... on CompanyLocationCatalog {
            companyLocations(first: 250) {
                nodes {
                    id
                    name
                }
            }
        }
    """ % CATALOG_BODY

    # Publication.name is deprecated. The merchant-facing label is Channel.name;
    # catalog.title is often a generated "Channel Catalog {id}" and is only a fallback.
    PUBLICATION_BODY = """
        id
        channels(first: 1) {
            nodes {
                id
                name
            }
        }
        catalog {
            %s
        }
    """ % CATALOG_BODY

    PUBLICATION_BODY_GET_PRODUCTS = """
        id
        products(first: 250) {
            nodes {
                id
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    """

    BODY_GET_PRICELIST_ITEMS = """
        id
        prices(first: 250, originType: FIXED) {
            nodes {
                %s
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    """ % PRICE_LIST_PRICE_BODY

    MONEY_V2_BODY = """
        amount
        currencyCode
    """

    MONEY_BAG_BODY = """
        presentmentMoney {
            %s
        }
        shopMoney {
            %s
        }
    """ % (MONEY_V2_BODY, MONEY_V2_BODY)

    DISCOUNT_ALLOCATION_BODY = """
        allocatedAmountSet {
            %s
        }
        discountApplication {
            ... on DiscountCodeApplication {
                code
            }
            ... on AutomaticDiscountApplication {
                title
            }
            ... on ManualDiscountApplication {
                title
            }
            ... on ScriptDiscountApplication {
                title
            }
        }
    """ % MONEY_BAG_BODY

    SELECTED_OPTION_BODY = """
        name
        value
        optionValue {
            %s
        }
    """ % PRODUCT_OPTION_VALUE_BODY

    PRODUCT_VARIANT_BODY = """
        id
        product {
            id
            hasOnlyDefaultVariant
        }
        availableForSale
        sku
        barcode
        price
        taxable
        title
        inventoryPolicy
        inventoryQuantity
        compareAtPrice
        inventoryItem {
            %s
        }
        selectedOptions {
            %s
        }
        metafields(first: 50) {
            nodes {
                %s
            }
        }
        media(first: 5) {
            nodes {
                %s
            }
        }
    """ % (
        INVENTORY_ITEM_BODY,
        SELECTED_OPTION_BODY,
        METAFIELD_BODY,
        MEDIA_BODY,
    )

    PRODUCT_GET_VARIANTS_BODY = """
        id
        variants(first: 250) {
            nodes {
                %s
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    """ % PRODUCT_VARIANT_BODY

    PRODUCT_VARIANT_MINIMAL_BODY_WITH_INVENTORY = """
        id
        inventoryItem {
            %s
        }
    """ % INVENTORY_ITEM_BODY

    PRODUCT_BODY = """
        id
        title
        status
        productType
        tags
        isGiftCard
        descriptionHtml
        vendor
        options {
            %s
        }
        collections(first: 25, query:"collection_type:custom") {
            nodes {
                %s
            }
        }
        category {
            %s
        }
        hasOnlyDefaultVariant
        variantsCount {
            count
        }
        featuredMedia {
            id
        }
        metafields(first: 50) {
            nodes {
                %s
            }
        }
        media(first: 250) {
            nodes {
                %s
            }
        }
        resourcePublications(first: 50) {
            nodes {
                publication {
                    %s
                }
            }
        }
        variants(first: 250) {
            nodes {
                %s
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    """ % (
        PRODUCT_OPTION_BODY,
        COLLECTION_BODY,
        TAXONOMY_CATEGORY_BODY,
        METAFIELD_BODY,
        MEDIA_BODY,
        PUBLICATION_BODY,
        PRODUCT_VARIANT_BODY,
    )

    PRODUCT_GET_ATTRIBUTES_BODY = """
        id
        options {
            %s
        }
    """ % PRODUCT_OPTION_BODY

    QUERY_BATCH_BY_IDS = """
        query($ids: [ID!]!) {
            nodes(ids: $ids) {
                ... on %s {
                    %s
                }
            }
        }
    """

    DELIVERY_PROVINCE_BODY = """
        id
        name
        code
    """

    DELIVERY_COUNTRY_BODY = """
        id
        name
        code {
            countryCode
            restOfWorld
        }
        provinces {
            %s
        }
    """ % DELIVERY_PROVINCE_BODY

    DELIVERY_ZONE_BODY = """
        id
        name
        countries {
            %s
        }
    """ % DELIVERY_COUNTRY_BODY

    DELIVERY_PROFILE_LOCATION_GROUP_BODY = """
        locationGroup {
            id
        }
        locationGroupZones(first: 100) {
            nodes {
                zone {
                    %s
                }
            }
        }
    """ % DELIVERY_ZONE_BODY

    DELIVERY_PROFILE_BODY = """
        id
        name
        profileLocationGroups {
            %s
        }
    """ % DELIVERY_PROFILE_LOCATION_GROUP_BODY

    TAX_LINE_BODY = """
        rate
        ratePercentage
        source
        title
        priceSet {
            %s
        }
    """ % MONEY_BAG_BODY

    SHIPPING_LINE_BODY = """
        id
        title
        code
        isRemoved
        carrierIdentifier
        originalPriceSet {
            %s
        }
        currentDiscountedPriceSet {
            %s
        }
        taxLines {
            %s
        }
        discountAllocations {
            %s
        }
    """ % (
        MONEY_BAG_BODY,
        MONEY_BAG_BODY,
        TAX_LINE_BODY,
        DISCOUNT_ALLOCATION_BODY,
    )

    # A page this full is the truncation signal Customer.get_addresses() uses to
    # decide whether to page a dedicated follow-up query -- keep in sync with it.
    # Most customers have a handful of addresses, and each query is billed by the
    # requested page size regardless of how many rows actually come back, so this
    # stays small rather than defaulting to Shopify's 250-per-connection ceiling.
    CUSTOMER_ADDRESSES_PAGE_SIZE = 10

    CUSTOMER_ADDRESSES_BODY = """
        addressesV2(first: %d) {
            nodes {
                %s
            }
        }
    """ % (CUSTOMER_ADDRESSES_PAGE_SIZE, MAILING_ADDRESS_BODY)

    CUSTOMER_BODY = """
        id
        firstName
        lastName
        displayName
        locale
        state
        taxExempt
        defaultEmailAddress {
            emailAddress
        }
        defaultPhoneNumber {
            phoneNumber
        }
        %s
        defaultAddress {
            id
        }
        metafields(first: 25) {
            nodes {
                %s
            }
        }
    """ % (
        CUSTOMER_ADDRESSES_BODY,
        METAFIELD_BODY,
    )

    FULFILLMENT_ORDER_LINE_ITEM_BODY = """
        id
        totalQuantity
        remainingQuantity
        sku
        lineItem {
            id
        }
    """

    DUTY_BODY = """
        id
        countryCodeOfOrigin
        harmonizedSystemCode
        price {
            %s
        }
        taxLines {
            %s
        }
    """ % (
        MONEY_BAG_BODY,
        TAX_LINE_BODY,
    )

    LINE_ITEM_BODY = """
        id
        name
        quantity
        isGiftCard
        currentQuantity
        taxable
        sku
        taxLines {
            %s
        }
        product {
            id
        }
        variant{
            id
            sku
            title
            product {
                id
            }
        }
        originalUnitPriceSet {
            %s
        }
        discountAllocations {
            %s
        }
        duties {
            %s
        }
    """ % (
        TAX_LINE_BODY,
        MONEY_BAG_BODY,
        DISCOUNT_ALLOCATION_BODY,
        DUTY_BODY,
    )

    LINE_ITEM_MINIMAL_BODY = """
        id
        sku
        quantity
        nonFulfillableQuantity
        variant {
            id
            product {
                id
            }
        }
    """

    FULFILLMENT_LINE_ITEM_BODY = """
        id
        quantity
        lineItem {
            %s
        }
    """ % LINE_ITEM_MINIMAL_BODY

    FULFILLMENT_BODY = """
        id
        name
        status
        displayStatus
        totalQuantity
        trackingInfo {
            number
            company
            url
        }
        order {
            id
        }
        fulfillmentOrders(first: 1) {
            nodes {
                id
            }
        }
        location {
            id
        }
        fulfillmentLineItems(first: 250) {
            nodes {
                %s
            }
        }
        service {
            id
            handle
            serviceName
            trackingSupport
            type
        }
        updatedAt
    """ % FULFILLMENT_LINE_ITEM_BODY

    DELIVERY_METHOD_BODY = """
        id
        presentedName
        methodType
        serviceCode
    """

    FULFILLMENT_ORDER_GET_DELIVERY_METHODS_BODY = """
        id
        deliveryMethod {
            %s
        }
    """ % DELIVERY_METHOD_BODY

    FULFILLMENT_ORDER_BODY = """
        id
        status
        orderId
        fulfillAt
        fulfillBy
        updatedAt
        lineItems(first: 250) {
            nodes {
                %s
            }
        }
        deliveryMethod {
            %s
        }
        assignedLocation {
            location {
                id
            }
        }
    """ % (
        FULFILLMENT_ORDER_LINE_ITEM_BODY,
        DELIVERY_METHOD_BODY,
    )

    ORDER_TRANSACTION_BODY = """
        id
        order {
            id
        }
        paymentId
        kind
        status
        gateway
        formattedGateway
        amountSet {
            %s
        }
        parentTransaction {
            id
            paymentId
        }
        processedAt
    """ % MONEY_BAG_BODY

    ORDER_RISK_SUMMARY_BODY = """
        assessments {
            facts {
                description
                sentiment
            }
            riskLevel
        }
        recommendation
    """

    ORDER_CUSTOM_ATTRIBUTE_BODY = """
        key
        value
    """

    BUSINESS_ENTITY_BODY = """
        id
        primary
        displayName
        companyName
    """

    ORDER_REFUND_BODY = """
        id
        createdAt
        note
        totalRefundedSet {
            %s
        }
        refundLineItems(first: 50) {
            edges {
                node {
                    quantity
                    restockType
                    location {
                        id
                        name
                    }
                    lineItem {
                        id
                        name
                        sku
                        quantity
                    }
                    priceSet {
                        %s
                    }
                    subtotalSet {
                        %s
                    }
                    totalTaxSet {
                        %s
                    }
                }
            }
        }
        refundShippingLines(first: 10) {
            edges {
                node {
                    id
                    subtotalAmountSet {
                        %s
                    }
                    taxAmountSet {
                        %s
                    }
                }
            }
        }
        transactions(first: 10) {
            edges {
                node {
                    id
                    kind
                    status
                    amountSet {
                        %s
                    }
                    parentTransaction {
                        id
                        kind
                    }
                    gateway
                    processedAt
                }
            }
        }
        return {
            id
            status
            name
        }
    """ % (
        MONEY_BAG_BODY,
        MONEY_BAG_BODY,
        MONEY_BAG_BODY,
        MONEY_BAG_BODY,
        MONEY_BAG_BODY,
        MONEY_BAG_BODY,
        MONEY_BAG_BODY,
    )

    ORDER_RETURN_BODY = """
        edges {
            node {
                id
                status
                name
                totalQuantity
                returnLineItems(first: 50) {
                    edges {
                        node {
                            ... on ReturnLineItem {
                                id
                                quantity
                                refundableQuantity
                                refundedQuantity
                                returnReason
                                returnReasonDefinition {
                                    handle
                                    name
                                }
                                returnReasonNote
                                fulfillmentLineItem {
                                    id
                                    lineItem {
                                        id
                                        name
                                        sku
                                    }
                                }
                            }
                        }
                    }
                }
                reverseFulfillmentOrders(first: 10) {
                    edges {
                        node {
                            id
                            status
                            reverseDeliveries(first: 10) {
                                edges {
                                    node {
                                        id
                                        deliverable {
                                            ... on ReverseDeliveryShippingDeliverable {
                                                tracking {
                                                    number
                                                    url
                                                    carrierName
                                                }
                                                label {
                                                    publicFileUrl
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    # Refund and return data is requested through a single slot so it can be left out entirely.
    # Reading returns needs the read_returns access scope, which stores that never enabled
    # returns sync have no reason to grant; refunds ride on read_orders but are parsed by the
    # same switch, so asking for either without the feature would be dead payload.
    # See ORDER_BODY / ORDER_BODY_NO_REFUNDS_RETURNS below.
    _ORDER_BODY_TMPL = """
        id
        name
        sourceName
        email
        phone
        confirmed
        cancelReason
        cancelledAt
        closedAt
        createdAt
        updatedAt
        processedAt
        displayFulfillmentStatus
        displayFinancialStatus
        customerLocale
        taxesIncluded
        taxExempt
        totalWeight
        confirmationNumber
        discountCode
        discountCodes
        currencyCode
        presentmentCurrencyCode
        requiresShipping
        tags
        note
        fullyPaid
        fulfillable
        canMarkAsPaid
        paymentGatewayNames
        billingAddressMatchesShippingAddress
        poNumber
        publication {
            %s
        }
        risk {
            %s
        }
        fulfillments(first: 25) {
            %s
        }

        fulfillmentOrders(first: 25) {
            nodes {
                %s
            }
        }
        currentTotalPriceSet {
            %s
        }
        dutiesIncluded
        totalPriceSet {
            %s
        }
        customer {
            %s
        }
        lineItems(first: 250) {
            nodes {
                %s
            }
        }
        billingAddress {
            %s
        }
        shippingAddress {
            %s
        }
        shippingLine {
            %s
        }
        transactions(first: 10) {
            %s
        }
        %s
        customAttributes {
            %s
        }
        merchantBusinessEntity {
            %s
        }
    """

    ORDER_BODY = _ORDER_BODY_TMPL % (
        PUBLICATION_BODY,
        ORDER_RISK_SUMMARY_BODY,
        FULFILLMENT_BODY,
        FULFILLMENT_ORDER_BODY,
        MONEY_BAG_BODY,
        MONEY_BAG_BODY,
        CUSTOMER_BODY,
        LINE_ITEM_BODY,
        MAILING_ADDRESS_BODY,
        MAILING_ADDRESS_BODY,
        SHIPPING_LINE_BODY,
        ORDER_TRANSACTION_BODY,
        """
        # Capped at 10 to limit GraphQL query cost; orders rarely exceed 3-4 refunds.
        refunds(first: 10) {
            %s
        }
        # Capped at 10 to limit GraphQL query cost; orders rarely exceed 3-4 returns.
        returns(first: 10) {
            %s
        }
        """ % (ORDER_REFUND_BODY, ORDER_RETURN_BODY),
        ORDER_CUSTOM_ATTRIBUTE_BODY,
        BUSINESS_ENTITY_BODY,
    )

    ORDER_BODY_NO_REFUNDS_RETURNS = _ORDER_BODY_TMPL % (
        PUBLICATION_BODY,
        ORDER_RISK_SUMMARY_BODY,
        FULFILLMENT_BODY,
        FULFILLMENT_ORDER_BODY,
        MONEY_BAG_BODY,
        MONEY_BAG_BODY,
        CUSTOMER_BODY,
        LINE_ITEM_BODY,
        MAILING_ADDRESS_BODY,
        MAILING_ADDRESS_BODY,
        SHIPPING_LINE_BODY,
        ORDER_TRANSACTION_BODY,
        '',
        ORDER_CUSTOM_ATTRIBUTE_BODY,
        BUSINESS_ENTITY_BODY,
    )

    ORDER_GET_TAXES_BODY = """
        id
        taxesIncluded
        taxLines {
            %s
        }
        shippingLines(first: 5) {
            nodes {
                id
                taxLines {
                    %s
                }
            }
        }
        lineItems(first: 10) {
            nodes {
                id
                taxLines {
                    %s
                }
            }
        }
    """ % (
        TAX_LINE_BODY,
        TAX_LINE_BODY,
        TAX_LINE_BODY,
    )

    ORDER_GET_DELIVERY_METHODS_BODY = """
        id
        shippingLine {
            %s
        }
        fulfillmentOrders(first: 10) {
            nodes {
                id
                deliveryMethod {
                    %s
                }
            }
        }
    """ % (
        SHIPPING_LINE_BODY,
        DELIVERY_METHOD_BODY,
    )

    ORDER_GET_PAYMENT_METHODS_BODY = """
        id
        name
        createdAt
        paymentGatewayNames
    """

    ORDER_INPUT_FILE_BODY = """
        id
        name
        publication {
            %s
        }
        merchantBusinessEntity {
            %s
        }
        displayFulfillmentStatus
        displayFinancialStatus
        cancelReason
        cancelledAt
        closedAt
        createdAt
        updatedAt
    """ % (PUBLICATION_BODY, BUSINESS_ENTITY_BODY)

    WEBHOOK_SUBSCRIPTION_BODY = """
        id
        topic
        uri
        format
        filter
        includeFields
        legacyResourceId
        createdAt
        updatedAt
    """

    # ==========MUTATION CREATE==================

    MUTATION_CREATE_PRODUCT_ASYNCHRONOUS = """
        mutation createProductAsynchronous($productSet: ProductSetInput!) {
            productSet(synchronous: true, input: $productSet) {
                product {
                    id
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_2

    MUTATION_FILE_CREATE = """
        mutation fileCreate($files: [FileCreateInput!]!) {
            fileCreate(files: $files) {
                files {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (FILE_BODY, USER_ERRORS_BODY_2)

    MUTATION_FILE_UPDATE = """
        mutation FileUpdate($input: [FileUpdateInput!]!) {
            fileUpdate(files: $input) {
                files {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (FILE_BODY, USER_ERRORS_BODY_2)

    MUTATION_PRODUCT_REORDER_MEDIA = """
        mutation productReorderMedia($id: ID!, $moves: [MoveInput!]!) {
            productReorderMedia(id: $id, moves: $moves) {
                job {
                    id
                }
                mediaUserErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_2

    MUTATION_PRODUCT_VARIANT_APPEND_MEDIA = """
        mutation productVariantAppendMedia($productId: ID!, $variantMedia: [ProductVariantAppendMediaInput!]!) {
            productVariantAppendMedia(productId: $productId, variantMedia: $variantMedia) {
                product {
                    id
                }
                productVariants {
                    id
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_2

    MUTATION_PRODUCT_VARIANT_DETACH_MEDIA = """
        mutation productVariantDetachMedia($productId: ID!, $variantMedia: [ProductVariantDetachMediaInput!]!) {
            productVariantDetachMedia(productId: $productId, variantMedia: $variantMedia) {
                product {
                    id
                }
                productVariants {
                    id
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_2

    MUTATION_STAGED_UPLOADS_CREATE = """
        mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
            stagedUploadsCreate(input: $input) {
                stagedTargets {
                    url
                    resourceUrl
                    parameters {
                        name
                        value
                    }
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    # ==========MUTATION DELETE==================

    MUTATION_WEBHOOK_SUBSCRIPTION_DELETE = """
        mutation webhookSubscriptionDelete($id: ID!) {
            webhookSubscriptionDelete(id: $id) {
                deletedWebhookSubscriptionId
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_DELETE_FILES = """
        mutation fileDelete($input: [ID!]!) {
            fileDelete(fileIds: $input) {
                deletedFileIds
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_2

    MUTATION_CANCEL_FULFILLMENT = """
        mutation fulfillmentCancel($id: ID!) {
            fulfillmentCancel(id: $id) {
                fulfillment {
                    id
                    status
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_UPDATE_ORDER = """
        mutation OrderUpdate($input: OrderInput!) {
            orderUpdate(input: $input) {
                order {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (ORDER_BODY, USER_ERRORS_BODY_1)

    # refundMethod (OrderCancelRefundMethodInput) carries the "Original payment method / Store
    # credit / Later" choice; omitting it means refund later (no refund issued now).
    MUTATION_CANCEL_ORDER = """
        mutation OrderCancel(
            $orderId: ID!,
            $reason: OrderCancelReason!,
            $restock: Boolean!,
            $notifyCustomer: Boolean,
            $staffNote: String,
            $refundMethod: OrderCancelRefundMethodInput
        ) {
            orderCancel(
                orderId: $orderId,
                reason: $reason,
                restock: $restock,
                notifyCustomer: $notifyCustomer,
                staffNote: $staffNote,
                refundMethod: $refundMethod
            ) {
                job {
                    id
                    done
                }
                orderCancelUserErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_2

    MUTATION_PRODUCT_DELETE = """
        mutation productDelete($id: ID!) {
            productDelete(input: {id: $id}) {
                deletedProductId
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_PRODUCT_UPDATE = """
        mutation UpdateProduct($product: ProductUpdateInput!) {
            productUpdate(product: $product) {
                product {
                    id
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_METAFIELDS_DELETE = """
        mutation MetafieldsDelete($metafields: [MetafieldIdentifierInput!]!) {
            metafieldsDelete(metafields: $metafields) {
                deletedMetafields {
                    ownerId
                    namespace
                    key
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_PRODUCT_VARIANT_DELETE = """
        mutation productVariantDelete($id: ID!) {
            productVariantDelete(id: $id) {
                deletedProductVariantId
                product {
                    id
                    title
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_BULK_CREATE_PRODUCT_VARIANTS = """
        mutation ProductVariantsCreate(
            $productId: ID!,
            $variants: [ProductVariantsBulkInput!]!,
        ) {
            productVariantsBulkCreate(
                productId: $productId,
                variants: $variants
            ) {
                productVariants {
                    id
                    title
                    selectedOptions {
                        name
                        value
                    }
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_BULK_UPDATE_PRODUCT_VARIANTS = """
        mutation productVariantsBulkUpdate(
            $productId: ID!,
            $variants: [ProductVariantsBulkInput!]!,
        ) {
            productVariantsBulkUpdate(
                productId: $productId,
                variants: $variants
            ) {
                product {
                    id
                }
                productVariants {
                    id
                    metafields(first: 50) {
                        nodes {
                            namespace
                            key
                            value
                        }
                    }
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_BULK_DELETE_PRODUCT_VARIANTS = """
        mutation bulkDeleteProductVariants(
            $productId: ID!,
            $variantsIds: [ID!]!
        ) {
            productVariantsBulkDelete(
                productId: $productId,
                variantsIds: $variantsIds
            ) {
                product {
                    id
                    title
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_CREATE_PRODUCT_OPTIONS = """
        mutation createOptions(
            $productId: ID!,
            $options: [OptionCreateInput!]!,
            $variantStrategy: ProductOptionCreateVariantStrategy
        ) {
            productOptionsCreate(
                productId: $productId,
                options: $options,
                variantStrategy: $variantStrategy
            ) {
                userErrors {
                    %s
                }
                product {
                    id
                    options {
                        id
                        name
                        values
                        position
                        optionValues {
                            %s
                        }
                    }
                }
            }
        }
    """ % (USER_ERRORS_BODY_2, PRODUCT_OPTION_VALUE_BODY)

    MUTATION_DELETE_PRODUCT_OPTIONS = """
        mutation deleteOptions(
            $productId: ID!,
            $options: [ID!]!,
            $strategy: ProductOptionDeleteStrategy
        ) {
            productOptionsDelete(
                productId: $productId,
                options: $options,
                strategy: $strategy
            ) {
                userErrors {
                    %s
                }
                deletedOptionsIds
                product {
                    id
                    options {
                        id
                        name
                        values
                        position
                        optionValues {
                            %s
                        }
                    }
                }
            }
        }
    """ % (USER_ERRORS_BODY_2, PRODUCT_OPTION_VALUE_BODY)

    MUTATION_UPDATE_PRODUCT_OPTIONS = """
        mutation updateOption(
            $productId: ID!,
            $option: OptionUpdateInput!,
            $optionValuesToAdd: [OptionValueCreateInput!],
            $optionValuesToDelete: [ID!]
            $variantStrategy: ProductOptionUpdateVariantStrategy
        ) {
            productOptionUpdate(
                productId: $productId,
                option: $option,
                optionValuesToAdd: $optionValuesToAdd,
                optionValuesToDelete: $optionValuesToDelete,
                variantStrategy: $variantStrategy
            ) {
                userErrors {
                    %s
                }
                product {
                    id
                    options {
                        id
                        name
                        values
                        position
                        optionValues {
                            %s
                        }
                    }
                }
            }
        }
    """ % (USER_ERRORS_BODY_2, PRODUCT_OPTION_VALUE_BODY)

    MUTATION_CREATE_STAGED_TARGET = """
        mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
            stagedUploadsCreate(input: $input) {
                stagedTargets {
                    url
                    resourceUrl
                    parameters {
                        name
                        value
                    }
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_INVENTORY_SET_QTY = """
        mutation InventorySet($input: InventorySetQuantitiesInput!) {
            inventorySetQuantities(input: $input) @idempotent(key: "%%s") {
                inventoryAdjustmentGroup {
                    createdAt
                    reason
                    referenceDocumentUri
                    changes {
                        name
                        delta
                    }
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_ACTIVATE_INVENTORY_ITEM = """
        mutation ActivateInventoryItem($inventoryItemId: ID!, $locationId: ID!, $available: Int) {
            inventoryActivate(
                inventoryItemId: $inventoryItemId, locationId: $locationId, available: $available
            ) @idempotent(key: "%%s") {
                inventoryLevel {
                    id
                    quantities(names: ["available"]) {
                        name
                        quantity
                    }
                    item {
                        id
                        tracked
                    }
                    location {
                        id
                    }
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_INVENTORY_ITEM_UPDATE = """
        mutation inventoryItemUpdate($id: ID!, $input: InventoryItemInput!) {
            inventoryItemUpdate(id: $id, input: $input) {
                inventoryItem {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (INVENTORY_ITEM_BODY, USER_ERRORS_BODY_1)

    MUTATION_FULFILLMENT_ORDER_SPLIT = """
        mutation fulfillmentOrderSplit($fulfillmentOrderSplits: [FulfillmentOrderSplitInput!]!) {
            fulfillmentOrderSplit(fulfillmentOrderSplits: $fulfillmentOrderSplits) {
                fulfillmentOrderSplits {
                    remainingFulfillmentOrder {
                        %s
                    }
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (FULFILLMENT_ORDER_BODY, USER_ERRORS_BODY_1)

    MUTATION_FULFILLMENT_ORDER_MOVE = """
        mutation fulfillmentOrderMove($id: ID!, $newLocationId: ID!) {
            fulfillmentOrderMove(id: $id, newLocationId: $newLocationId) {
                movedFulfillmentOrder {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (FULFILLMENT_ORDER_BODY, USER_ERRORS_BODY_1)

    MUTATION_FULFILLMENT_CREATE = """
        mutation fulfillmentCreate($fulfillment: FulfillmentInput!, $message: String) {
            fulfillmentCreate(fulfillment: $fulfillment, message: $message) {
                fulfillment {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (FULFILLMENT_BODY, USER_ERRORS_BODY_1)

    MUTATION_FULFILLMENT_UPDATE = """
        mutation FulfillmentTrackingInfoUpdate($fulfillmentId: ID!, $trackingInfoInput: FulfillmentTrackingInput!, $notifyCustomer: Boolean) {
            fulfillmentTrackingInfoUpdate(fulfillmentId: $fulfillmentId, trackingInfoInput: $trackingInfoInput, notifyCustomer: $notifyCustomer) {
                fulfillment {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (FULFILLMENT_BODY, USER_ERRORS_BODY_1)

    # Return export (Odoo → Shopify).
    # returnCreate creates a Return on the storefront. Logistics-only: refund stays
    # in Shopify. One returnCreate call → one Return node, with one
    # reverseFulfillmentOrder needed for the follow-up tracking attachment.
    MUTATION_RETURN_CREATE = """
        mutation returnCreate($returnInput: ReturnInput!) {
            returnCreate(returnInput: $returnInput) {
                return {
                    id
                    status
                    reverseFulfillmentOrders(first: 1) {
                        edges {
                            node {
                                id
                                lineItems(first: 50) {
                                    edges {
                                        node {
                                            id
                                            totalQuantity
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    # Attaches a ReverseDelivery (merchant-paid shipping with tracking info) to an existing
    # reverseFulfillmentOrder produced by returnCreate. The trackingInput's carrierName is
    # a free-text string that Shopify maps to its tracking-link database when recognised
    # (UPS, FedEx, DHL, USPS, ...) — we send delivery.carrier.shopify_code so the merchant
    # controls the mapping. Unrecognised names render as plain text in the customer email.
    MUTATION_REVERSE_DELIVERY_CREATE_WITH_SHIPPING = """
        mutation reverseDeliveryCreateWithShipping(
            $reverseFulfillmentOrderId: ID!,
            $reverseDeliveryLineItems: [ReverseDeliveryLineItemInput!]!,
            $trackingInput: ReverseDeliveryTrackingInput,
            $notifyCustomer: Boolean
        ) {
            reverseDeliveryCreateWithShipping(
                reverseFulfillmentOrderId: $reverseFulfillmentOrderId,
                reverseDeliveryLineItems: $reverseDeliveryLineItems,
                trackingInput: $trackingInput,
                notifyCustomer: $notifyCustomer
            ) {
                reverseDelivery {
                    id
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    # Minimal query used at export time to build a
    # {sale.order.line external id -> fulfillmentLineItem GID} lookup. Uses Shopify's own
    # "returnable" endpoint rather than the order body's plain `fulfillments` connection
    # (used elsewhere, e.g. ORDER_BODY): `returnableFulfillments` already excludes
    # fulfillments that can't be returned (CANCELLED/ERROR/FAILURE — confirmed empirically
    # against a live store: a cancelled fulfillment's line item never appears here, even
    # with its full quantity never claimed by any return), so there is no client-side
    # status filter to maintain. Its `returnableFulfillmentLineItems.quantity` is the
    # quantity still available to be returned right now — net of every prior return
    # against that line, open or closed — not the total ever fulfilled, so a return
    # export can catch an over-claim here instead of learning about it only when
    # Shopify's returnCreate mutation rejects the call.
    QUERY_FULFILLMENT_LINE_ITEMS_FOR_EXPORT = """
        query getReturnableFulfillmentLineItemsForExport($id: ID!) {
            returnableFulfillments(orderId: $id, first: 50) {
                nodes {
                    returnableFulfillmentLineItems(first: 250) {
                        edges {
                            node {
                                quantity
                                fulfillmentLineItem {
                                    id
                                    lineItem {
                                        id
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    MUTATION_MARK_AS_PAID = """
        mutation orderMarkAsPaid($input: OrderMarkAsPaidInput!) {
            orderMarkAsPaid(input: $input) {
                order {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (ORDER_BODY, USER_ERRORS_BODY_1)

    MUTATION_COLLECTION_CREATE = """
        mutation CollectionCreate($collection: CollectionCreateInput!) {
            collectionCreate(collection: $collection) {
                collection {
                    id
                    title
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_WEBHOOK_SUBSCRIPTION_CREATE = """
        mutation webhookSubscriptionCreate(
            $topic: WebhookSubscriptionTopic!,
            $webhookSubscription: WebhookSubscriptionInput!
        ) {
            webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
                webhookSubscription {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (WEBHOOK_SUBSCRIPTION_BODY, USER_ERRORS_BODY_1)

    MUTATION_CREATE_PRICE_LIST = """
        mutation PriceListCreate($input: PriceListCreateInput!) {
            priceListCreate(input: $input) {
                priceList {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (PRICELIST_BODY, USER_ERRORS_BODY_2)

    MUTATION_UPDATE_PRICE_LIST = """
        mutation priceListUpdate($id: ID!, $input: PriceListUpdateInput!) {
            priceListUpdate(id: $id, input: $input) {
                priceList {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (PRICELIST_BODY, USER_ERRORS_BODY_2)

    MUTATION_UPDATE_FIXED_PRICES = """
        mutation priceListFixedPricesUpdate($priceListId: ID!, $pricesToAdd: [PriceListPriceInput!]!, $variantIdsToDelete: [ID!]!) {
            priceListFixedPricesUpdate(priceListId: $priceListId, pricesToAdd: $pricesToAdd, variantIdsToDelete: $variantIdsToDelete) {
                deletedFixedPriceVariantIds
                pricesAdded {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (PRICE_LIST_PRICE_BODY, USER_ERRORS_BODY_1)

    MUTATION_UPDATE_FIXED_PRICES_BY_PRODUCT = """
        mutation priceListFixedPricesByProductUpdate($pricesToAdd: [PriceListProductPriceInput!], $pricesToDeleteByProductIds: [ID!], $priceListId: ID!) {
            priceListFixedPricesByProductUpdate(pricesToAdd: $pricesToAdd, pricesToDeleteByProductIds: $pricesToDeleteByProductIds, priceListId: $priceListId) {
                pricesToDeleteProducts {
                    id
                }
                pricesToAddProducts {
                    id
                }
                userErrors {
                    %s
                }
            }
        }
    """ % USER_ERRORS_BODY_1

    MUTATION_PUBLICATION_UPDATE = """
        mutation publicationUpdate($id: ID!, $input: PublicationUpdateInput!) {
            publicationUpdate(id: $id, input: $input) {
                publication {
                    %s
                }
                userErrors {
                    %s
                }
            }
        }
    """ % (PUBLICATION_BODY, USER_ERRORS_BODY_1)

    # --- Shopify Payments payouts (RDCN-1288) ---

    SHOPIFY_PAYMENTS_ACCOUNT_BODY = """
        id
        defaultCurrency
    """

    SHOPIFY_PAYMENTS_PAYOUT_SUMMARY_BODY = """
        chargesGross { %s }
        chargesFee { %s }
        refundsFeeGross { %s }
        refundsFee { %s }
        adjustmentsGross { %s }
        adjustmentsFee { %s }
        reservedFundsGross { %s }
        reservedFundsFee { %s }
        retriedPayoutsGross { %s }
        retriedPayoutsFee { %s }
        advanceGross { %s }
        advanceFees { %s }
        usdcRebateCreditAmount { %s }
    """ % ((MONEY_V2_BODY,) * 13)

    SHOPIFY_PAYMENTS_PAYOUT_BODY = """
        id
        legacyResourceId
        issuedAt
        status
        transactionType
        externalTraceId
        net { %s }
        summary {
            %s
        }
    """ % (MONEY_V2_BODY, SHOPIFY_PAYMENTS_PAYOUT_SUMMARY_BODY)

    SHOPIFY_PAYMENTS_BALANCE_TRANSACTION_BODY = """
        id
        type
        sourceType
        adjustmentReason
        sourceId
        sourceOrderTransactionId
        test
        transactionDate
        amount { %s }
        fee { %s }
        net { %s }
        associatedOrder { id name }
        associatedPayout { id status }
    """ % (MONEY_V2_BODY, MONEY_V2_BODY, MONEY_V2_BODY)
