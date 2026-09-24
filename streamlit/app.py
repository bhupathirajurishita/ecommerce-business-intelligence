from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "olist_analytics.db"
REPORTS = ROOT / "reports"

st.set_page_config(page_title="Olist Business Intelligence", page_icon="📦", layout="wide")
st.title("Olist E-Commerce Business Intelligence")
st.caption("Historical marketplace data | Sep 2016–Oct 2018 | Descriptive analysis")


def show_published_dashboard():
    """Render from privacy-safe aggregate reports when the local database is unavailable."""
    required = {
        "metrics": "dashboard_metrics.csv",
        "monthly": "monthly_sales.csv",
        "categories": "category_sales.csv",
        "states": "state_sales.csv",
        "products": "top_products.csv",
        "payments": "payment_methods.csv",
        "reviews": "review_distribution.csv",
        "delivery": "delivery_review.csv",
        "category_delivery": "category_delivery.csv",
    }
    missing = [name for name in required.values() if not (REPORTS / name).exists()]
    if missing:
        st.error("Published summary files are missing: " + ", ".join(missing))
        st.info("Run the project data preparation steps locally, then publish the aggregate reports.")
        st.stop()

    data = {key: pd.read_csv(REPORTS / filename) for key, filename in required.items()}
    metrics = data["metrics"].iloc[0]
    st.info(
        "Showing the published aggregate dashboard. Detailed filters are available when the "
        "processed database is present locally. Only summary data is needed for this hosted view."
    )
    k = st.columns(4)
    k[0].metric("Product revenue", f"R$ {metrics.product_revenue:,.2f}")
    k[1].metric("Delivered orders", f"{int(metrics.delivered_orders):,}")
    k[2].metric("Average order value", f"R$ {metrics.average_order_value:,.2f}")
    k[3].metric("Average review score", f"{metrics.average_order_review:.2f}/5")
    st.caption("Revenue is item price only; freight and recorded payment value are separate measures.")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Executive Overview", "Sales Analytics", "Customer & Payments", "Delivery & Experience"]
    )
    with tab1:
        a, b = st.columns(2)
        monthly = data["monthly"].copy()
        monthly["month"] = monthly["month"].astype(str)
        a.plotly_chart(
            px.line(monthly, x="month", y="product_revenue", markers=True,
                    title="Monthly delivered product revenue"),
            use_container_width=True,
        )
        b.plotly_chart(
            px.bar(monthly, x="month", y="orders", title="Monthly delivered orders"),
            use_container_width=True,
        )
        a, b = st.columns(2)
        a.metric("Average delivery time", f"{metrics.average_delivery_days:.2f} days")
        b.metric("Late delivery share", f"{metrics.late_delivery_rate:.1%}")
    with tab2:
        a, b = st.columns(2)
        categories = data["categories"].sort_values("product_revenue", ascending=False)
        a.plotly_chart(
            px.bar(categories.head(15).sort_values("product_revenue"),
                   x="product_revenue", y="category", orientation="h",
                   title="Top categories by delivered product revenue"),
            use_container_width=True,
        )
        b.plotly_chart(
            px.bar(data["products"].head(15).sort_values("product_revenue"),
                   x="product_revenue", y="product_id", orientation="h",
                   hover_data=["category", "orders"], title="Top products by revenue"),
            use_container_width=True,
        )
        st.dataframe(categories, use_container_width=True, hide_index=True)
    with tab3:
        a, b = st.columns(2)
        states = data["states"].sort_values("product_revenue", ascending=False)
        a.plotly_chart(
            px.bar(states.head(15), x="state", y="product_revenue",
                   title="Delivered product revenue by customer state"),
            use_container_width=True,
        )
        b.plotly_chart(
            px.bar(data["payments"], x="payment_type", y="recorded_payment_value",
                   title="Recorded payment value by method"),
            use_container_width=True,
        )
        st.caption("Payment value can include freight and may be split across records or methods.")
    with tab4:
        a, b = st.columns(2)
        a.plotly_chart(
            px.bar(data["delivery"], x="delivery_result", y="avg_review_score",
                   title="Average review score by delivery result",
                   hover_data=["orders"]),
            use_container_width=True,
        )
        b.plotly_chart(
            px.bar(data["reviews"], x="review_score", y="orders",
                   title="Order-level review score distribution"),
            use_container_width=True,
        )
        cat_delivery = data["category_delivery"].sort_values("avg_delivery_days")
        st.plotly_chart(
            px.bar(cat_delivery, x="avg_delivery_days", y="category", orientation="h",
                   title="Average delivery time by category", hover_data=["orders"]),
            use_container_width=True,
        )


if not DB.exists():
    show_published_dashboard()
    st.stop()


@st.cache_data
def load(name):
    with sqlite3.connect(DB) as con:
        return pd.read_sql_query(f"SELECT * FROM {name}", con)


orders = load("fact_orders")
items = load("fact_order_items")
customers = load("dim_customers")
payments = load("fact_payments")
reviews = load("fact_reviews")
products = load("dim_products")
# Prepare safe order-level values before interactive filtering.
orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"], errors="coerce")
orders["order_month"] = orders["order_purchase_timestamp"].dt.to_period("M").astype(str)
items["order_id"] = items.order_id.astype(str)
orders["order_id"] = orders.order_id.astype(str)
orders["customer_id"] = orders.customer_id.astype(str)
items["item_revenue"] = pd.to_numeric(items.price, errors="coerce")
orders["delivery_days"] = pd.to_numeric(orders.delivery_days, errors="coerce")
orders["delivery_late"] = orders.delivery_late.map({1: True, 0: False, "1": True, "0": False, True: True, False: False})

st.sidebar.header("Filters")
months = sorted(orders.order_month.dropna().unique())
month_range = st.sidebar.select_slider("Purchase month range", options=months, value=(months[0], months[-1]))
states = sorted(customers.customer_state.dropna().unique())
selected_states = st.sidebar.multiselect("Customer state", states, default=[])
categories = sorted(items.category_english.dropna().unique())
selected_categories = st.sidebar.multiselect("Product category", categories, default=[])
status_options = sorted(orders.order_status.dropna().unique())
selected_status = st.sidebar.multiselect("Order status", status_options, default=["delivered"] if "delivered" in status_options else status_options)

orders_f = orders[orders.order_month.between(month_range[0], month_range[1]) & orders.order_status.isin(selected_status)].copy()
customers_f = customers.copy()
if selected_states:
    customers_f = customers_f[customers_f.customer_state.isin(selected_states)]
orders_f = orders_f[orders_f.customer_id.isin(customers_f.customer_id.astype(str))]
items_f = items[items.order_id.isin(orders_f.order_id)]
if selected_categories:
    items_f = items_f[items_f.category_english.isin(selected_categories)]
# Recalculate order set after category filter so order counts follow selected product slice.
orders_scope = orders_f[orders_f.order_id.isin(items_f.order_id)] if selected_categories else orders_f
revenue = items_f.item_revenue.sum()
order_count = orders_scope.order_id.nunique()
customer_lookup = customers_f[["customer_id", "customer_unique_id"]].drop_duplicates("customer_id")
customer_ids = orders_scope.merge(customer_lookup, on="customer_id", how="left").customer_unique_id.nunique()
aov = revenue / order_count if order_count else 0

k = st.columns(4)
k[0].metric("Product revenue", f"R$ {revenue:,.2f}")
k[1].metric("Orders", f"{order_count:,}")
k[2].metric("Identified customers", f"{customer_ids:,}")
k[3].metric("Average order value", f"R$ {aov:,.2f}")
st.caption("Revenue is item price only; freight and recorded payment value are separate measures.")

tab1, tab2, tab3, tab4 = st.tabs(["Executive Overview", "Sales Analytics", "Customer Analytics", "Delivery & Experience"])
with tab1:
    a, b = st.columns(2)
    monthly_items = items_f.merge(orders_scope[["order_id", "order_month"]], on="order_id", how="inner", validate="many_to_one").groupby("order_month", as_index=False).agg(revenue=("item_revenue", "sum"))
    a.plotly_chart(px.line(monthly_items, x="order_month", y="revenue", markers=True, title="Monthly product revenue"), use_container_width=True)
    monthly_orders = orders_scope.groupby("order_month", as_index=False).order_id.nunique().rename(columns={"order_id": "orders"})
    b.plotly_chart(px.bar(monthly_orders, x="order_month", y="orders", title="Monthly orders"), use_container_width=True)
    if not orders_scope.empty:
        avg_score = reviews[reviews.order_id.astype(str).isin(orders_scope.order_id)].review_score.mean()
        delivered = orders_scope[(orders_scope.order_status == "delivered") & orders_scope.delivery_days.notna()]
        late_rate = delivered.delivery_late.eq(True).mean() if len(delivered) else float("nan")
        k2 = st.columns(3); k2[0].metric("Average review score", f"{avg_score:.2f}/5" if pd.notna(avg_score) else "—"); k2[1].metric("Avg delivery", f"{delivered.delivery_days.mean():.1f} days" if len(delivered) else "—"); k2[2].metric("Late rate (dated deliveries)", f"{late_rate:.1%}" if pd.notna(late_rate) else "—")
with tab2:
    a, b = st.columns(2)
    cat = items_f.groupby("category_english", as_index=False).agg(revenue=("item_revenue", "sum"), orders=("order_id", "nunique")).sort_values("revenue", ascending=False)
    a.plotly_chart(px.bar(cat.head(15), x="revenue", y="category_english", orientation="h", title="Top categories by product revenue"), use_container_width=True)
    prod = items_f.groupby("product_id", as_index=False).agg(revenue=("item_revenue", "sum"), lines=("order_id", "size")).sort_values("revenue", ascending=False).head(15)
    b.plotly_chart(px.bar(prod, x="revenue", y="product_id", orientation="h", title="Top products by product revenue"), use_container_width=True)
    st.dataframe(cat, use_container_width=True, hide_index=True)
with tab3:
    state_orders = orders_scope.merge(customers_f[["customer_id", "customer_unique_id", "customer_state"]], on="customer_id", how="left", validate="many_to_one")
    state_items = items_f.merge(state_orders[["order_id", "customer_state", "customer_unique_id"]], on="order_id", how="inner", validate="many_to_one")
    state = state_items.groupby("customer_state", as_index=False).agg(revenue=("item_revenue", "sum"), orders=("order_id", "nunique"), customers=("customer_unique_id", "nunique")).sort_values("revenue", ascending=False)
    st.plotly_chart(px.bar(state.head(20), x="customer_state", y="revenue", title="Product revenue by customer state"), use_container_width=True)
    st.dataframe(state, use_container_width=True, hide_index=True)
with tab4:
    delivered = orders_scope[(orders_scope.order_status == "delivered") & orders_scope.delivery_days.notna()]
    a, b = st.columns(2)
    a.metric("Average delivery time", f"{delivered.delivery_days.mean():.2f} days" if len(delivered) else "—")
    late_n = delivered.delivery_late.eq(True).sum()
    b.metric("Late delivery share", f"{late_n / len(delivered):.1%}" if len(delivered) else "—")
    review_order = reviews[reviews.order_id.astype(str).isin(delivered.order_id)].groupby("order_id", as_index=False).review_score.mean().rename(columns={"review_score": "avg_review_score"})
    scatter = delivered.merge(review_order, on="order_id", how="inner", validate="one_to_one")
    st.plotly_chart(px.scatter(scatter, x="delivery_days", y="avg_review_score", color="delivery_late", opacity=.35, title="Delivery time and order-level review score", labels={"delivery_days":"Delivery days","avg_review_score":"Average review score","delivery_late":"Late"}), use_container_width=True)
    category_orders = items_f.groupby(["order_id", "category_english"], as_index=False).agg(item_revenue=("price", "sum"))
    category_delivery = category_orders.merge(delivered[["order_id", "delivery_days"]], on="order_id", how="inner", validate="many_to_one").groupby("category_english", as_index=False).agg(avg_delivery_days=("delivery_days", "mean"), orders=("order_id", "nunique")).sort_values("avg_delivery_days", ascending=False)
    st.plotly_chart(px.bar(category_delivery, x="avg_delivery_days", y="category_english", orientation="h", title="Average delivery time by product category"), use_container_width=True)
    category_review = category_orders.merge(review_order, on="order_id", how="inner", validate="many_to_one").groupby("category_english", as_index=False).agg(avg_review_score=("avg_review_score", "mean"), orders=("order_id", "nunique")).sort_values("avg_review_score")
    st.plotly_chart(px.bar(category_review, x="avg_review_score", y="category_english", orientation="h", title="Average order review score by category"), use_container_width=True)
    scores = reviews[reviews.order_id.astype(str).isin(orders_scope.order_id)].review_score.value_counts().sort_index().rename_axis("score").reset_index(name="reviews")
    st.plotly_chart(px.bar(scores, x="score", y="reviews", title="Review score distribution"), use_container_width=True)

st.divider()
st.subheader("Payment analysis")
pay_scope = payments[payments.order_id.astype(str).isin(orders_scope.order_id)]
pay_summary = pay_scope.groupby("payment_type", as_index=False).agg(recorded_value=("payment_value", "sum"), payment_records=("order_id", "size"), avg_installments=("payment_installments", "mean"))
st.plotly_chart(px.bar(pay_summary, x="payment_type", y="recorded_value", title="Recorded payment value by method"), use_container_width=True)
st.dataframe(pay_summary, use_container_width=True, hide_index=True)
