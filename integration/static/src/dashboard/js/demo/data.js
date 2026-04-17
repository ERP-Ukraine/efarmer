/** @odoo-module **/

export const DEMO_SALES_CARDS = [
    {
        "title": "Total Sales Revenue",
        "value": 65330,
        "percent": 34.0,
        "currency_symbol": "$",
    },
    {
        "title": "Number of Orders",
        "value": 573,
        "percent": 21.0,
        "currency_symbol": "$",
    },
    {
        "title": "Average / Median Order Value",
        "value": {
            "average": 200,
            "median": 150,
        },
        "percent": 13.0,
        "currency_symbol": "$",
    },
    {
        "title": "Repeat Purchase Rate",
        "value": 11.0,
        "percent": -22.0,
        "currency_symbol": "$",
    },
];

export const DEMO_SALES_DATA = {
    sales_over_time: {
        labels: ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"],
        values: [1000, 1500, 1200, 2000, 2200, 2500],
        currency_symbol: "$",
    },
    order_value_distribution: {
        labels: ["0 to 400, $", "401 to 700, $", "More than 700, $"],
        values: [50, 90, 40],
        currency_symbol: "$",
    },
};

export const DEMO_PRODUCTS = {
    products: [
        {
            id: 1,
            name: "Example Product A",
            default_code: "EX-A",
            units_sold: 10,
            total_revenue: 5000,
            percent_total: 25,
            currency_symbol: "$",
        },
        {
            id: 2,
            name: "Example Product B",
            default_code: "EX-B",
            units_sold: 20,
            total_revenue: 8000,
            percent_total: 40,
            currency_symbol: "$",
        },
    ]
};

export const DEMO_STORE_PERFORMANCE = {
    stores: [
        {
            name: "Example Store 1",
            orders: 10,
            sales_revenue: 5000,
            average_order_value: 500,
            median_order_value: 400,
            currency_symbol: "$",
        },
        {
            name: "Example Store 2",
            orders: 20,
            sales_revenue: 8000,
            average_order_value: 400,
            median_order_value: 350,
            currency_symbol: "$",
        },
    ],
    countries: [
        { name: "Country A", percent: 50 },
        { name: "Country B", percent: 30 },
        { name: "Country C", percent: 20 },
    ],
    customers: {
        labels: ["New Customers", "Returning Customers"],
        values: [40, 60],
    },
};
