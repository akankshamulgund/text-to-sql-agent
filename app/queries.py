from datetime import date

import pandas as pd
import streamlit as st

from tools.db import get_connection


DATE_FILTER = "o_orderdate BETWEEN ? AND ?"


@st.cache_data
def date_bounds():
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT MIN(o_orderdate), MAX(o_orderdate) FROM orders"
        ).fetchone()
    finally:
        connection.close()


def _query_dataframe(query, parameters):
    connection = get_connection()
    try:
        return connection.execute(query, parameters).df()
    finally:
        connection.close()


@st.cache_data
def kpis(start_date: date, end_date: date):
    query = f"""
        SELECT
            COALESCE(SUM(o_totalprice), 0) AS total_revenue,
            COUNT(*) AS order_count,
            COALESCE(AVG(o_totalprice), 0) AS average_order_value,
            COUNT(DISTINCT o_custkey) AS customer_count
        FROM orders
        WHERE {DATE_FILTER}
    """
    return _query_dataframe(query, [start_date, end_date]).iloc[0].to_dict()


@st.cache_data
def monthly_revenue(start_date: date, end_date: date):
    return _query_dataframe(
        f"""
        SELECT
            DATE_TRUNC('month', o_orderdate)::DATE AS month,
            SUM(o_totalprice) AS revenue
        FROM orders
        WHERE {DATE_FILTER}
        GROUP BY 1
        ORDER BY 1
        """,
        [start_date, end_date],
    )


@st.cache_data
def revenue_by_region(start_date: date, end_date: date):
    return _query_dataframe(
        f"""
        SELECT
            r_name AS region,
            SUM(o_totalprice) AS revenue
        FROM orders
        JOIN customer ON o_custkey = c_custkey
        JOIN nation ON c_nationkey = n_nationkey
        JOIN region ON n_regionkey = r_regionkey
        WHERE {DATE_FILTER}
        GROUP BY 1
        ORDER BY revenue DESC
        """,
        [start_date, end_date],
    )


@st.cache_data
def top_customers(start_date: date, end_date: date):
    return _query_dataframe(
        f"""
        SELECT
            o_custkey AS customer_id,
            SUM(o_totalprice) AS revenue
        FROM orders
        WHERE {DATE_FILTER}
        GROUP BY 1
        ORDER BY revenue DESC
        LIMIT 10
        """,
        [start_date, end_date],
    )


@st.cache_data
def orders_by_priority(start_date: date, end_date: date):
    return _query_dataframe(
        f"""
        SELECT
            o_orderpriority AS priority,
            COUNT(*) AS order_count
        FROM orders
        WHERE {DATE_FILTER}
        GROUP BY 1
        ORDER BY 1
        """,
        [start_date, end_date],
    )


@st.cache_data
def recent_orders(start_date: date, end_date: date):
    return _query_dataframe(
        f"""
        SELECT
            o_orderkey AS order_id,
            o_custkey AS customer_id,
            o_orderstatus AS status,
            o_totalprice AS total_price,
            o_orderdate AS order_date,
            o_orderpriority AS priority
        FROM orders
        WHERE {DATE_FILTER}
        ORDER BY o_orderdate DESC, o_orderkey DESC
        LIMIT 20
        """,
        [start_date, end_date],
    )
