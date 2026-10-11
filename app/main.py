from datetime import date
from pathlib import Path
import sys

import streamlit as st

# Make project-level packages available when Streamlit runs this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from charts import (
    orders_by_priority,
    result_chart,
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
from agents.pipeline import run_pipeline


st.set_page_config(page_title="AI Analytics Dashboard", layout="wide")

with st.sidebar:
    st.header("Agent pipeline")
    schema_agent_enabled = st.toggle("Schema agent", value=True)
    validator_enabled = st.toggle("Validator agent", value=True)

st.title("AI Analytics Dashboard")
st.subheader("Ask your data")
with st.form("ask_your_data", clear_on_submit=False):
    question = st.text_input("Ask a business question", placeholder="e.g. Which region had the highest revenue?")
    ask_submitted = st.form_submit_button("Ask")

if ask_submitted:
    if not question.strip():
        st.warning("Enter a question about your data.")
    else:
        with st.spinner("Analyzing your question..."):
            st.session_state["sql_agent_result"] = run_pipeline(
                question.strip(),
                {
                    "schema_agent": schema_agent_enabled,
                    "validator": validator_enabled,
                    "max_validator_retries": 2,
                    "max_steps": 5,
                },
            )

agent_result = st.session_state.get("sql_agent_result")
if agent_result:
    if agent_result["error"]:
        st.error(agent_result["error"])
    if agent_result["answer"]:
        st.markdown(agent_result["answer"])
    if agent_result["dataframe"] is not None:
        st.dataframe(agent_result["dataframe"], width="stretch", hide_index=True)
        chart = result_chart(agent_result["dataframe"])
        if chart is not None:
            st.plotly_chart(chart, width="stretch")
    with st.expander("Show agent steps"):
        for trace in agent_result.get("agents_trace", []):
            st.markdown(
                f"**{trace['agent_name']}** ({trace['seconds']:.2f}s, "
                f"{trace['llm_calls_used']} LLM call(s))"
            )
            st.write("Input:", trace["input_summary"])
            st.write("Output:", trace["output_summary"])
        for trace in agent_result["steps"]:
            st.markdown(
                f"**Step {trace['step']}: {trace['tool_name']}** "
                f"({trace['seconds']:.2f}s)"
            )
            st.write("Arguments:", trace["arguments"])
            st.write("Result:", trace["result_summary"])
        if agent_result["sql"]:
            st.markdown("**Final SQL**")
            st.code(agent_result["sql"], language="sql")

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
