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

    SHOP_BODY = """
        id
        url
        name
        email
        weightUnit
        ianaTimezone
        timezoneOffset
        taxesIncluded
        taxShipping
        currencyCode
        billingAddress {
            %s
        }
        productTags(first: 250) {
            nodes
        }
    """ % MAILING_ADDRESS_BODY

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
        variant {
            id
            product {
                id
            }
        }
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
        }
    """ % INVENTORY_ITEM_BODY

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
                        id
                        name
                    }
                }
            }
        }
    """ % CURRENCY_SETTING_BODY

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

    # The `name` field is deprecated, use `catalog.title` instead. But the lack of the `catalog` FK happens..
    PUBLICATION_BODY = """
        id
        name
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

    MONEY_BAG_BODY = """
        presentmentMoney {
            amount
            currencyCode
        }
        shopMoney {
            amount
            currencyCode
        }
    """

    DISCOUNT_ALLOCATION_BODY = """
        allocatedAmountSet {
            %s
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
        options {
            %s
        }
        collections(first: 25, query:"collection_type:custom") {
            nodes {
                %s
            }
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
        variants(first: 250) {
            nodes {
                %s
            }
        }
    """ % (
        PRODUCT_OPTION_BODY,
        COLLECTION_BODY,
        METAFIELD_BODY,
        MEDIA_BODY,
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
        carrierIdentifier
        currentDiscountedPriceSet {
            %s
        }
        taxLines {
            %s
        }
    """ % (
        MONEY_BAG_BODY,
        TAX_LINE_BODY,
    )

    CUSTOMER_BODY = """
        id
        email
        firstName
        lastName
        displayName
        phone
        locale
        state
        taxExempt
        addresses {
            %s
        }
        defaultAddress {
            id
        }
        metafields(first: 25) {
            nodes {
                %s
            }
        }
    """ % (
        MAILING_ADDRESS_BODY,
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
    """ % (
        TAX_LINE_BODY,
        MONEY_BAG_BODY,
        DISCOUNT_ALLOCATION_BODY,
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

    ORDER_BODY = """
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
        returnStatus
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
    """ % (
        PUBLICATION_BODY,
        ORDER_RISK_SUMMARY_BODY,
        FULFILLMENT_BODY,
        FULFILLMENT_ORDER_BODY,
        MONEY_BAG_BODY,
        CUSTOMER_BODY,
        LINE_ITEM_BODY,
        MAILING_ADDRESS_BODY,
        MAILING_ADDRESS_BODY,
        SHIPPING_LINE_BODY,
        ORDER_TRANSACTION_BODY,
    )

    ORDER_GET_TAXES_BODY = """
        id
        taxesIncluded
        taxLines {
            %s
        }
        shippingLines(first: 5) {
            nodes {
                %s
            }
        }
        lineItems(first: 250) {
            nodes {
                %s
            }
        }
    """ % (
        TAX_LINE_BODY,
        SHIPPING_LINE_BODY,
        LINE_ITEM_BODY,
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
        displayFulfillmentStatus
        displayFinancialStatus
        returnStatus
        cancelReason
        cancelledAt
        closedAt
        createdAt
        updatedAt
    """ % PUBLICATION_BODY

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

    MUTATION_CANCEL_ORDER = """
        mutation OrderCancel {
            orderCancel(
                orderId: "gid://shopify/Order/%%s",
                notifyCustomer: %%s,
                refund: %%s,
                restock: %%s,
                reason: %%s,
                staffNote: "%%s"
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
        ) {
            productOptionsCreate(
                productId: $productId,
                options: $options
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
                            id
                            name
                            hasVariants
                        }
                    }
                }
            }
        }
    """ % USER_ERRORS_BODY_2

    MUTATION_DELETE_PRODUCT_OPTIONS = """
        mutation deleteOptions(
            $productId: ID!,
            $options: [ID!]!,
        ) {
            productOptionsDelete(
                productId: $productId,
                options: $options
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
                            id
                            name
                        hasVariants
                        }
                    }
                }
            }
        }
    """ % USER_ERRORS_BODY_2

    MUTATION_UPDATE_PRODUCT_OPTIONS = """
        mutation updateOption(
            $productId: ID!,
            $option: OptionUpdateInput!,
            $optionValuesToDelete: [ID!]
            $variantStrategy: ProductOptionUpdateVariantStrategy
        ) {
            productOptionUpdate(
                productId: $productId,
                option: $option,
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
                            id
                            name
                            hasVariants
                        }
                    }
                }
            }
        }
    """ % USER_ERRORS_BODY_2

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
            inventorySetQuantities(input: $input) {
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
            inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId, available: $available) {
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
        mutation CollectionCreate($input: CollectionInput!) {
            collectionCreate(input: $input) {
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
