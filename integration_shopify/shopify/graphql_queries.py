#  See LICENSE file for full copyright and licensing details.


class GraphQlQuery:
    """GraphQl query templates"""

    METAFIELDS_BY_OBJECT_QUERY_TEMPLATE = """
        {
            %s(id: "gid://shopify/%s/%s") {
                metafields (first:250) {
                    edges {
                        node {
                            id,
                            key,
                            value,
                        }
                    }
                }
            }
        }
    """

    METAFIELDS_QUERY_TEMPLATE = """
        {
            metafieldDefinitions(first: 250, ownerType: %s) {
                edges {
                    node {
                        id,
                        name,
                        key,
                        namespace,
                        type {
                            name,
                        }
                    }
                }
            }
        }
    """

    TAXES_FROM_ORDERS_QUERY_TEMPLATE = """
        {
            orders(%s) {
                pageInfo {
                    endCursor
                }
                edges {
                    node {
                        id
                        name
                        createdAt
                        taxesIncluded
                        taxLines {
                            title
                            price
                            rate
                            ratePercentage
                        }
                        lineItems(first: 250) {
                            edges {
                                node {
                                    taxLines {
                                        title
                                        price
                                        rate
                                        ratePercentage
                                    }
                                }
                            }
                        }
                        shippingLines(first: 250) {
                            edges {
                                node {
                                    taxLines {
                                        title
                                        price
                                        rate
                                        ratePercentage
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    PAYMENT_METHODS_FROM_ORDERS_QUERY_TEMPLATE = """
        {
            orders(%s) {
                pageInfo {
                    endCursor
                }
                edges {
                    node {
                        id
                        name
                        createdAt
                        paymentGatewayNames
                    }
                }
            }
        }
    """

    DELIVERY_METHODS_FROM_ORDERS_QUERY_TEMPLATE = """
        {
            orders(%s) {
                pageInfo {
                    endCursor
                }
                edges {
                    node {
                        id
                        name
                        createdAt
                        shippingLines(first: 250) {
                            nodes {
                                id
                                title
                                code
                            }
                        }
                    }
                }
            }
        }
    """

    ORDER_RISKS_FROM_ORDERS_QUERY_TEMPLATE = """
        {
            order(id: "gid://shopify/Order/%s") {
                id
                name
                risk {
                    assessments {
                        facts {
                            description
                            sentiment
                        }
                        riskLevel
                    }
                    recommendation
                }
            }
        }
    """

    GET_FEATURE_VALUES = """
        {
            shop {
                productTags(first: 250) {
                    edges {
                        node
                    }
                }
            }
        }
    """

    PRODUCT_ID_BY_REFERENCE = """
        {
            productVariants(first: 1, query: "%s:%s") {
                edges
                {
                    node {
                        id
                        %s
                        product {
                            id
                        }
                    }
                }
            }
        }
    """

    MUTATION_DROP_PRODUCT_MEDIA_IMAGES = """
        mutation productDeleteMedia($mediaIds: [ID!]!, $productId: ID!) {
            productDeleteMedia(mediaIds: $mediaIds, productId: $productId) {
                deletedProductImageIds
                mediaUserErrors {
                    field
                    message
                }
            }
        }
    """

    QUERY_GET_PRODUCT_MEDIA_IMAGES_IDS = """
        {
            product(id: "gid://shopify/Product/%s") {
                id
                media (first: 250) {
                    edges {
                        node {
                            id
                        }
                    }
                }
            }
        }
    """

    CANCEL_FULFILLMENT = """
        mutation fulfillmentCancel {
            fulfillmentCancel(id: "gid://shopify/Fulfillment/%s") {
                fulfillment {
                    id
                    status
                }
                userErrors {
                    field
                    message
                }
            }
        }
    """

    CANCEL_ORDER = """
        mutation OrderCancel {
            orderCancel(
                orderId: "gid://shopify/Order/%s",
                notifyCustomer: %s,
                refund: %s,
                restock: %s,
                reason: %s,
                staffNote: "%s"
            ) {
                job {
                    id
                    done
                }
                orderCancelUserErrors {
                    field
                    message
                    code
                }
            }
        }
    """

    ORDER_BY_ID = """
    {
        order(id: "gid://shopify/Order/%s") {
            id
            name
            displayFinancialStatus
            displayFulfillmentStatus
            returnStatus
        }
    }
    """  # TODO: handle the `returnStatus`

    GET_SALE_CHANNELS = """
        {
            publications(first: 250) {
                edges {
                    node {
                        id
                        name
                    }
                }
            }
        }
    """

    CHANNEL_ID_FROM_ORDERS = """
        {
            orders(%s) {
                pageInfo {
                    endCursor
                }
                edges {
                    node {
                        id
                        publication {
                            id
                        }
                    }
                }
            }
        }
    """

    CHANNEL_ID_FROM_ORDER = """
        {
            order(%s) {
                id
                publication {
                    id
                }
            }
        }
    """
