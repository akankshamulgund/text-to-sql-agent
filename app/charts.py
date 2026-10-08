import plotly.express as px
import pandas as pd


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


def result_chart(dataframe):
    """Build a simple chart when a SQL result has one numeric measure."""
    if dataframe is None or len(dataframe.columns) != 2:
        return None

    numeric_columns = [
        column for column in dataframe.columns
        if pd.api.types.is_numeric_dtype(dataframe[column])
    ]
    if len(numeric_columns) != 1:
        return None

    value_column = numeric_columns[0]
    label_column = next(column for column in dataframe.columns if column != value_column)
    labels = dataframe[label_column]
    parsed_dates = pd.to_datetime(labels, errors="coerce")
    looks_like_dates = (
        not pd.api.types.is_numeric_dtype(labels)
        and len(labels) > 0
        and parsed_dates.notna().all()
    )
    if looks_like_dates:
        chart_data = dataframe.copy()
        chart_data[label_column] = parsed_dates
        return px.line(chart_data, x=label_column, y=value_column, markers=True)
    return px.bar(dataframe, x=label_column, y=value_column)
