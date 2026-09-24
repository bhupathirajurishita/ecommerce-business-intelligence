from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
DATE_COLS = {
    "orders": ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"],
    "items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}
FILES = {
    "customers": "olist_customers_dataset.csv", "geolocation": "olist_geolocation_dataset.csv",
    "items": "olist_order_items_dataset.csv", "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv", "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv", "sellers": "olist_sellers_dataset.csv",
    "translation": "product_category_name_translation.csv",
}

def read_table(name: str) -> pd.DataFrame:
    path = RAW / FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Missing expected source file: {path}")
    # Postal prefixes are identifiers, not measures; preserve zero padding.
    dtype = {c: "string" for c in ["customer_zip_code_prefix", "seller_zip_code_prefix", "geolocation_zip_code_prefix"]}
    df = pd.read_csv(path, dtype=dtype, low_memory=False)
    for c in DATE_COLS.get(name, []):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def audit_tables(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in tables.items():
        rows.append({
            "table": name, "rows": len(df), "columns": len(df.columns),
            "duplicate_full_rows": int(df.duplicated().sum()),
            "missing_cells": int(df.isna().sum().sum()),
            "missing_by_column": "; ".join(f"{c}={n}" for c, n in df.isna().sum().items() if n),
            "date_ranges": "; ".join(f"{c}: {df[c].min()} to {df[c].max()}" for c in DATE_COLS.get(name, []) if c in df),
        })
    return pd.DataFrame(rows)

def main() -> None:
    t = {name: read_table(name) for name in FILES}
    orders, items, payments, reviews = t["orders"], t["items"], t["payments"], t["reviews"]
    customers, products, sellers = t["customers"], t["products"], t["sellers"]

    # Keep the geographic source at postal-prefix grain by using coordinate medians.
    geo = t["geolocation"].groupby("geolocation_zip_code_prefix", as_index=False).agg(
        latitude=("geolocation_lat", "median"), longitude=("geolocation_lng", "median"),
        )
    translation = t["translation"]
    dim_customers = customers.merge(geo, left_on="customer_zip_code_prefix", right_on="geolocation_zip_code_prefix", how="left", validate="many_to_one")
    dim_customers = dim_customers.drop(columns=["geolocation_zip_code_prefix"], errors="ignore")
    dim_products = products.merge(translation, on="product_category_name", how="left", validate="many_to_one")
    dim_products["category_english"] = dim_products["product_category_name_english"].fillna(dim_products["product_category_name"]).fillna("Unknown").astype("string").str.replace("_", " ", regex=False).str.strip().str.title()

    # Independent fact tables preserve their natural grains; do not join payments/reviews to item lines.
    fact_orders = orders.merge(customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left", validate="many_to_one")
    fact_orders["purchase_date"] = fact_orders["order_purchase_timestamp"].dt.strftime("%Y-%m-%d")
    fact_orders["purchase_month"] = fact_orders["order_purchase_timestamp"].dt.to_period("M").astype("string")
    fact_orders["delivery_days"] = (fact_orders["order_delivered_customer_date"] - fact_orders["order_purchase_timestamp"]).dt.total_seconds() / 86400
    delivered = fact_orders["order_status"].eq("delivered") & fact_orders["order_delivered_customer_date"].notna()
    fact_orders["delivery_late"] = pd.Series(pd.NA, index=fact_orders.index, dtype="boolean")
    fact_orders.loc[delivered, "delivery_late"] = fact_orders.loc[delivered, "order_delivered_customer_date"].gt(fact_orders.loc[delivered, "order_estimated_delivery_date"])

    fact_items = items.merge(dim_products[["product_id", "category_english"]], on="product_id", how="left", validate="many_to_one")
    fact_items["item_revenue"] = fact_items["price"]
    fact_items["item_total_with_freight"] = fact_items["price"] + fact_items["freight_value"]
    fact_payments = payments.copy()
    fact_reviews = reviews.copy()
    fact_reviews["review_creation_date"] = pd.to_datetime(fact_reviews["review_creation_date"], errors="coerce")
    fact_reviews["review_answer_timestamp"] = pd.to_datetime(fact_reviews["review_answer_timestamp"], errors="coerce")
    fact_reviews_by_order = fact_reviews.groupby("order_id", as_index=False).agg(avg_review_score=("review_score", "mean"), review_records=("review_id", "size"))
    fact_order_category = fact_items.groupby(["order_id", "category_english"], as_index=False).agg(category_product_revenue=("price", "sum"), category_freight=("freight_value", "sum"), item_lines=("order_item_id", "size"))
    fact_order_category = fact_order_category.merge(fact_orders[["order_id", "order_status", "delivery_days", "delivery_late"]], on="order_id", how="left", validate="many_to_one")
    fact_order_category = fact_order_category.merge(fact_reviews_by_order[["order_id", "avg_review_score"]], on="order_id", how="left", validate="many_to_one")
    dim_category = pd.DataFrame({"category_english": sorted(set(dim_products["category_english"].dropna()) | set(fact_items["category_english"].dropna()))})

    OUT.mkdir(parents=True, exist_ok=True)
    date_values = pd.date_range(fact_orders["order_purchase_timestamp"].min().normalize(), fact_orders["order_purchase_timestamp"].max().normalize(), freq="D")
    dim_date = pd.DataFrame({"date": date_values.strftime("%Y-%m-%d"), "year": date_values.year, "quarter": "Q" + date_values.quarter.astype(str), "month_number": date_values.month, "month_name": date_values.strftime("%B"), "year_month": date_values.strftime("%Y-%m"), "year_month_sort": date_values.year * 100 + date_values.month})
    processed = {"dim_date": dim_date, "dim_customers": dim_customers, "dim_products": dim_products, "dim_category": dim_category,
                 "dim_sellers": sellers, "dim_geolocation": geo,
                 "fact_orders": fact_orders, "fact_order_items": fact_items,
                 "fact_payments": fact_payments, "fact_reviews": fact_reviews, "fact_reviews_by_order": fact_reviews_by_order, "fact_order_category": fact_order_category}
    for name, df in processed.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
    audit = audit_tables(t)
    audit.to_csv(OUT / "data_quality_audit.csv", index=False)

    checks = {
        "orders_without_customer": int((~orders.customer_id.isin(customers.customer_id)).sum()),
        "items_without_order": int((~items.order_id.isin(orders.order_id)).sum()),
        "items_without_product": int((~items.product_id.isin(products.product_id)).sum()),
        "items_without_seller": int((~items.seller_id.isin(sellers.seller_id)).sum()),
        "payments_without_order": int((~payments.order_id.isin(orders.order_id)).sum()),
        "reviews_without_order": int((~reviews.order_id.isin(orders.order_id)).sum()),
        "duplicate_order_primary_keys": int(orders.order_id.duplicated().sum()),
        "duplicate_customer_primary_keys": int(customers.customer_id.duplicated().sum()),
        "duplicate_item_composite_keys": int(items.duplicated(["order_id", "order_item_id"]).sum()),
        "duplicate_payment_composite_keys": int(payments.duplicated(["order_id", "payment_sequential"]).sum()),
        "duplicate_product_primary_keys": int(products.product_id.duplicated().sum()),
        "duplicate_seller_primary_keys": int(sellers.seller_id.duplicated().sum()),
        "repeated_review_id_rows": int(reviews.review_id.duplicated().sum()),
        "geolocation_exact_duplicate_rows": int(t["geolocation"].duplicated().sum()),
        "seller_zip_without_geo": int((~sellers.seller_zip_code_prefix.isin(t["geolocation"].geolocation_zip_code_prefix)).sum()),
        "customer_zip_without_geo": int(dim_customers.latitude.isna().sum()),
        "product_categories_without_translation": int((products.product_category_name.notna() & ~products.product_category_name.isin(translation.product_category_name)).sum()),
    }
    pd.Series(checks, name="count").rename_axis("check").to_csv(OUT / "relationship_checks.csv")

    # A convenient local SQL database; separate fact tables avoid join fan-out.
    with sqlite3.connect(OUT / "olist_analytics.db") as con:
        for name, df in processed.items():
            df.to_sql(name, con, if_exists="replace", index=False)
        audit.to_sql("data_quality_audit", con, if_exists="replace", index=False)
    print(f"Loaded {len(t)} raw tables; wrote {len(processed)} analytical tables.")
    print(f"Database: {OUT / 'olist_analytics.db'}")
    print("Relationship checks:", checks)

if __name__ == "__main__":
    main()






