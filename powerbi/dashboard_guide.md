# Power BI Dashboard Guide

## Tables and relationships

Import the twelve CSV tables from `data/processed/`: `dim_date`, `dim_customers`, `dim_products`, `dim_category`, `dim_sellers`, `dim_geolocation`, `fact_orders`, `fact_order_items`, `fact_order_category`, `fact_payments`, `fact_reviews`, and `fact_reviews_by_order`.

Create single-direction relationships:

- `dim_date[date]` → `fact_orders[purchase_date]`
- `dim_customers[customer_id]` → `fact_orders[customer_id]`
- `fact_orders[order_id]` → `fact_order_items[order_id]`, `fact_order_category[order_id]`, `fact_payments[order_id]`, `fact_reviews[order_id]`, and `fact_reviews_by_order[order_id]`
- `dim_products[product_id]` → `fact_order_items[product_id]`
- `dim_category[category_english]` → `fact_order_items[category_english]` and `fact_order_category[category_english]`
- `dim_sellers[seller_id]` → `fact_order_items[seller_id]`
- `dim_geolocation[geolocation_zip_code_prefix]` → `dim_customers[customer_zip_code_prefix]` (optional map coordinates)

Do not join the raw payment or review rows into item lines. Use `fact_order_category` for category-level delivery and order-level review comparisons; it intentionally has one row for each order-category combination. Use `fact_reviews_by_order` when each order should have equal weight in a score average.

## Suggested DAX measures

```DAX
Product Revenue = SUM(fact_order_items[price])
Freight Value = SUM(fact_order_items[freight_value])
Orders = DISTINCTCOUNT(fact_orders[order_id])
Delivered Orders = CALCULATE([Orders], fact_orders[order_status] = "delivered")
Orders with Selected Items = DISTINCTCOUNT(fact_order_items[order_id])
Customers = DISTINCTCOUNT(fact_orders[customer_unique_id])
Average Order Value = DIVIDE([Product Revenue], [Orders])
Selected Category AOV = DIVIDE([Product Revenue], [Orders with Selected Items])
Average Delivery Days = AVERAGE(fact_orders[delivery_days])
Late Delivered Orders = CALCULATE([Orders], fact_orders[order_status] = "delivered", fact_orders[delivery_late] = TRUE())
Dated Delivered Orders = CALCULATE([Orders], fact_orders[order_status] = "delivered", NOT(ISBLANK(fact_orders[delivery_late])))
Late Delivery Rate = DIVIDE([Late Delivered Orders], [Dated Delivered Orders])
Average Order Review = AVERAGE(fact_reviews_by_order[avg_review_score])
Category Delivery Days = CALCULATE(AVERAGE(fact_order_category[delivery_days]), fact_order_category[order_status] = "delivered")
Category Review Score = AVERAGE(fact_order_category[avg_review_score])
Payment Value = SUM(fact_payments[payment_value])
```

`Average Order Value` is an all-order product-revenue measure. On category-filtered visuals, use `Selected Category AOV` and label it as category revenue per order containing that category. Payment-type filters should drive payment visuals; they do not change product revenue. Review-score filters should drive review visuals.

## Page 1 — Executive Overview

Cards: Product Revenue, Delivered Orders, Customers, Average Order Value, Average Order Review, Average Delivery Days. Add a monthly product-revenue line chart, monthly orders column chart, top-category revenue bars, and state revenue bars. Slicers: purchase date, customer state, and order status.

## Page 2 — Sales & Product Analytics

Category revenue and distinct orders, top products by item price, monthly product-revenue trend, and revenue by customer state. Add product-category slicer here. Use item price for product revenue; keep freight in its own measure.

## Page 3 — Customer Analytics

Customer counts and orders by customer state, revenue by customer state, and a table of state, identified unique customers, orders, and product revenue. Map with state codes or aggregated postal-prefix coordinates only if Power BI resolves Brazilian geography correctly; otherwise use ranked bars. Repeat buyer analysis uses `customer_unique_id`, while `customer_id` is order-specific.

## Page 4 — Delivery & Customer Experience

Show average delivery time and dated late-delivery rate, category delivery time, review-score distribution, order-level review score by delivery result, and a scatter plot of delivery days versus average order review. Add category and review-score filters to the relevant visuals. Show payment method and installment analysis in a separate section or page with its own payment-type slicer, using `fact_payments` only.

## Formatting

Use a restrained navy/blue/teal palette, format currency as Brazilian reais (R$), sort year-month by `year_month_sort`, and title measures with their denominator/scope. Avoid interpreting recorded payment value as product revenue. The dashboard guide and data tables are supplied; Power BI Desktop is needed to assemble and save the `.pbix` report.
