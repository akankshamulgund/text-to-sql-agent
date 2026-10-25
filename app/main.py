from datetime import date
from pathlib import Path
import sys

import streamlit as st

# Make project-level packages available when Streamlit runs this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import ensure_database
from charts import (
    orders_by_priority,
    render_chart,
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
from app.pins import add_pin, list_pins, remove_pin, run_pinned_query


ensure_database()
st.set_page_config(page_title="AI Analytics Dashboard", layout="wide")

with st.sidebar:
    st.header("Agent pipeline")
    st.caption("Demo uses public TPC-H sample data only.")
    planner_enabled = st.toggle("Planner", value=True)
    schema_agent_enabled = st.toggle("Schema agent", value=True)
    validator_enabled = st.toggle("Validator agent", value=True)
    insight_agent_enabled = st.toggle("Insight agent", value=True)
    visualization_agent_enabled = st.toggle("Visualization agent", value=True)

st.title("AI Analytics Dashboard")
st.subheader("Ask your data")
with st.form("ask_your_data", clear_on_submit=False):
    question = st.text_input("Ask a business question", placeholder="e.g. Which region had the highest revenue?")
    ask_submitted = st.form_submit_button("Ask")

if ask_submitted:
    if not question.strip():
        st.warning("Enter a question about your data.")
    elif st.session_state.get("questions_used", 0) >= 10:
        st.info("This demo allows 10 questions per session. Start a new session to ask more.")
    else:
        st.session_state["questions_used"] = st.session_state.get("questions_used", 0) + 1
        pipeline_config = {
            "planner": planner_enabled,
            "schema_agent": schema_agent_enabled,
            "validator": validator_enabled,
            "insight": insight_agent_enabled,
            "viz_agent": visualization_agent_enabled,
            "max_validator_retries": 2,
            "max_steps": 5,
        }
        st.session_state["last_question"] = question.strip()
        st.session_state["last_pipeline_config"] = pipeline_config
        with st.spinner("Analyzing your question..."):
            st.session_state["sql_agent_result"] = run_pipeline(
                question.strip(),
                pipeline_config,
            )

agent_result = st.session_state.get("sql_agent_result")
if agent_result:
    needs_clarification = agent_result.get("needs_clarification", False)
    if needs_clarification:
        st.info(agent_result.get("clarifying_question") or "Please clarify your question.")
        with st.form("clarification_form", clear_on_submit=True):
            clarification = st.text_input("Your clarification")
            clarification_submitted = st.form_submit_button("Continue")
        if clarification_submitted and clarification.strip():
            original_question = st.session_state.get("last_question", "")
            clarified_question = f"{original_question}\nClarification: {clarification.strip()}"
            st.session_state["last_question"] = clarified_question
            with st.spinner("Replanning with your clarification..."):
                st.session_state["sql_agent_result"] = run_pipeline(
                    clarified_question,
                    st.session_state.get("last_pipeline_config", {}),
                )
            st.rerun()
    else:
        if agent_result["error"]:
            st.error(agent_result["error"])
        if agent_result["answer"]:
            st.markdown(agent_result["answer"])
        if agent_result.get("insight"):
            st.markdown("**Insight**")
            st.markdown(agent_result["insight"])
        if agent_result.get("sql") and not agent_result.get("error"):
            if st.button("Pin to dashboard", key="pin_current_answer"):
                chart_spec = agent_result.get("chart_spec") or {
                    "type": "table",
                    "x": None,
                    "y": None,
                    "color": None,
                    "title": "Query result",
                }
                add_pin(
                    st.session_state.get("last_question", ""),
                    agent_result["sql"],
                    chart_spec,
                )
                st.success("Pinned to dashboard.")
        if agent_result["dataframe"] is not None:
            chart_spec = agent_result.get("chart_spec")
            chart = render_chart(chart_spec, agent_result["dataframe"]) if chart_spec else None
            if chart is not None:
                st.plotly_chart(chart, width="stretch")
            if not chart_spec or chart_spec.get("type") != "table":
                st.dataframe(agent_result["dataframe"], width="stretch", hide_index=True)

    with st.expander("Show agent steps"):
        planner_decision = agent_result.get("planner_decision")
        if planner_decision:
            st.markdown(
                f"**Planner decision:** `{planner_decision['category']}` — "
                f"{planner_decision['reason']}"
            )
        st.caption(
            f"Total: {agent_result.get('total_seconds', 0.0):.2f}s · "
            f"{agent_result.get('llm_calls', 0)} LLM calls · "
            f"~{agent_result.get('estimated_tokens', 0)} estimated tokens"
        )
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
pinned_items = list_pins()
if not pinned_items:
    st.caption("Pinned dashboard tiles will appear here.")
for offset in range(0, len(pinned_items), 2):
    tile_columns = st.columns(2)
    for column, pin in zip(tile_columns, pinned_items[offset:offset + 2]):
        with column:
            with st.container(border=True):
                chart_spec = pin.get("chart_spec") or {
                    "type": "table",
                    "title": pin["question"],
                }
                st.markdown(f"**{chart_spec.get('title') or pin['question']}**")
                st.caption(pin["question"])
                pinned_result = run_pinned_query(pin["sql"])
                if not pinned_result.get("ok"):
                    st.warning(
                        f"Pinned query unavailable: {pinned_result.get('error', 'Query failed.')}"
                    )
                else:
                    chart = render_chart(chart_spec, pinned_result["dataframe"])
                    if chart is not None:
                        st.plotly_chart(
                            chart,
                            width="stretch",
                            key=f"pin_chart_{pin['id']}",
                        )
                if st.button("Remove", key=f"remove_pin_{pin['id']}"):
                    remove_pin(pin["id"])
                    run_pinned_query.clear()
                    st.rerun()
