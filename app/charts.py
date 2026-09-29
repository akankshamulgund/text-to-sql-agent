import plotly.express as px


def revenue_over_time(dataframe):
    return px.line(
        dataframe,
        x="month",
        y="revenue",
        markers=True,
        title="Monthly Revenue",
        labels={"month": "Month", "revenue": "Revenue"},
    )


def revenue_by_region(dataframe):
    return px.bar(
        dataframe,
        x="region",
        y="revenue",
        title="Revenue by Region",
        labels={"region": "Region", "revenue": "Revenue"},
        text_auto=".2s",
    )


def top_customers(dataframe):
    return px.bar(
        dataframe.sort_values("revenue"),
        x="revenue",
        y="customer_id",
        orientation="h",
        title="Top 10 Customers by Revenue",
        labels={"customer_id": "Customer", "revenue": "Revenue"},
        text_auto=".2s",
    )


def orders_by_priority(dataframe):
    return px.bar(
        dataframe,
        x="priority",
        y="order_count",
        title="Orders by Priority",
        labels={"priority": "Order Priority", "order_count": "Orders"},
        text_auto=True,
    )
