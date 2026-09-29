from datetime import date
from pathlib import Path
import sys

import streamlit as st

# Make project-level packages available when Streamlit runs this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from charts import (
    orders_by_priority,
    revenue_by_region,
    revenue_over_time,
    top_customers,
)
from queries import (
    date_bounds,
    kpis,
    monthly_revenue,
    orders_by_priority as query_orders_by_priority,
    recent_orders,
    revenue_by_region as query_revenue_by_region,
    top_customers as query_top_customers,
)


st.set_page_config(page_title="AI Analytics Dashboard", layout="wide")

st.title("AI Analytics Dashboard")
st.subheader("Ask your data")
st.text_input("Ask a business question", placeholder="Coming soon", disabled=True)

minimum_date, maximum_date = date_bounds()
with st.sidebar:
    st.header("Filters")
    selected_dates = st.date_input(
        "Order date range",
        value=(minimum_date, maximum_date),
        min_value=minimum_date,
        max_value=maximum_date,
    )

if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
else:
    start_date = end_date = selected_dates

if not isinstance(start_date, date) or not isinstance(end_date, date):
    st.error("Select a valid order date range.")
    st.stop()

metrics = kpis(start_date, end_date)
metric_columns = st.columns(4)
metric_columns[0].metric("Total revenue", f"${metrics['total_revenue']:,.2f}")
metric_columns[1].metric("Orders", f"{int(metrics['order_count']):,}")
metric_columns[2].metric("Average order value", f"${metrics['average_order_value']:,.2f}")
metric_columns[3].metric("Customers", f"{int(metrics['customer_count']):,}")

st.divider()

monthly_data = monthly_revenue(start_date, end_date)
region_data = query_revenue_by_region(start_date, end_date)
customer_data = query_top_customers(start_date, end_date)
priority_data = query_orders_by_priority(start_date, end_date)

chart_column_one, chart_column_two = st.columns(2)
with chart_column_one:
    st.plotly_chart(revenue_over_time(monthly_data), width="stretch")
with chart_column_two:
    st.plotly_chart(revenue_by_region(region_data), width="stretch")

chart_column_three, chart_column_four = st.columns(2)
with chart_column_three:
    st.plotly_chart(top_customers(customer_data), width="stretch")
with chart_column_four:
    st.plotly_chart(orders_by_priority(priority_data), width="stretch")

st.subheader("Recent orders")
st.dataframe(recent_orders(start_date, end_date), width="stretch", hide_index=True)

st.subheader("Pinned tiles")
st.caption("Pinned dashboard tiles will appear here in a future version.")
