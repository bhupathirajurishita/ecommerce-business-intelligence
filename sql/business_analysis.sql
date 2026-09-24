-- Tables retain their source grain. Never join raw order_items, payments, and reviews together.
-- Run against data/processed/olist_analytics.db.

-- 1. Monthly gross product revenue and order count (delivered orders only).
SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month,
       ROUND(SUM(i.price), 2) AS product_revenue,
       COUNT(DISTINCT o.order_id) AS orders
FROM fact_orders o JOIN fact_order_items i USING (order_id)
WHERE o.order_status = 'delivered'
GROUP BY month ORDER BY month;

-- 2. Category revenue and order reach; revenue is item price, freight excluded.
SELECT p.category_english AS category,
       ROUND(SUM(i.price), 2) AS product_revenue,
       COUNT(DISTINCT i.order_id) AS orders,
       SUM(1) AS item_lines
FROM fact_order_items i JOIN dim_products p USING (product_id)
JOIN fact_orders o USING (order_id)
WHERE o.order_status = 'delivered'
GROUP BY category ORDER BY product_revenue DESC;

-- 3. Best-selling products by revenue.
SELECT p.product_id, p.category_english, ROUND(SUM(i.price), 2) AS product_revenue,
       COUNT(DISTINCT i.order_id) AS orders, COUNT(*) AS item_lines
FROM fact_order_items i JOIN dim_products p USING (product_id)
JOIN fact_orders o USING (order_id)
WHERE o.order_status = 'delivered'
GROUP BY p.product_id, p.category_english
ORDER BY product_revenue DESC LIMIT 20;

-- 4. State revenue; one order may contain several valid item lines.
SELECT c.customer_state AS state, ROUND(SUM(i.price), 2) AS product_revenue,
       COUNT(DISTINCT o.order_id) AS orders,
       COUNT(DISTINCT c.customer_unique_id) AS identified_customers
FROM fact_orders o JOIN dim_customers c USING (customer_id)
JOIN fact_order_items i USING (order_id)
WHERE o.order_status = 'delivered'
GROUP BY state ORDER BY product_revenue DESC;

-- 5. Delivery KPIs; denominator is delivered orders with both timestamps.
SELECT ROUND(AVG(delivery_days), 2) AS avg_delivery_days,
       SUM(CASE WHEN delivery_late = 1 THEN 1 ELSE 0 END) AS late_orders,
       COUNT(*) AS delivered_orders_with_dates,
       ROUND(100.0 * SUM(CASE WHEN delivery_late = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS late_pct
FROM fact_orders
WHERE order_status = 'delivered' AND delivery_days IS NOT NULL AND delivery_late IS NOT NULL;

-- 6. Review score distribution by order. Average multiple reviews within each order first.
WITH per_order AS (
  SELECT order_id, AVG(review_score) AS order_review_score
  FROM fact_reviews GROUP BY order_id
)
SELECT order_review_score, COUNT(*) AS orders
FROM per_order GROUP BY order_review_score ORDER BY order_review_score;

-- 7. Delivery performance versus customer rating, one row per order.
WITH reviews_by_order AS (
  SELECT order_id, AVG(review_score) AS avg_review_score FROM fact_reviews GROUP BY order_id
)
SELECT CASE WHEN o.delivery_late = 1 THEN 'Late'
            WHEN o.delivery_late = 0 THEN 'On time or early'
            ELSE 'Unknown / not delivered' END AS delivery_result,
       ROUND(AVG(r.avg_review_score), 2) AS avg_review_score,
       COUNT(*) AS orders
FROM fact_orders o LEFT JOIN reviews_by_order r USING (order_id)
GROUP BY delivery_result ORDER BY orders DESC;

-- 8. Payment method use/value. Payment rows are the grain; order count can overlap across methods.
SELECT payment_type, COUNT(*) AS payment_records,
       COUNT(DISTINCT order_id) AS orders_using_method,
       ROUND(SUM(payment_value), 2) AS recorded_payment_value,
       ROUND(AVG(payment_installments), 2) AS avg_installments
FROM fact_payments GROUP BY payment_type ORDER BY recorded_payment_value DESC;

-- 9. Installment patterns.
SELECT payment_installments, COUNT(*) AS payment_records,
       ROUND(SUM(payment_value), 2) AS recorded_payment_value
FROM fact_payments GROUP BY payment_installments ORDER BY payment_installments;

-- 10. Category delivery and rating: first reduce each order to one rating, then join to order/category.
WITH reviews_by_order AS (
  SELECT order_id, AVG(review_score) AS avg_review_score FROM fact_reviews GROUP BY order_id
), order_category AS (
  SELECT order_id, category_english, SUM(price) AS category_revenue
  FROM fact_order_items GROUP BY order_id, category_english
)
SELECT oc.category_english AS category,
       ROUND(AVG(o.delivery_days), 2) AS avg_delivery_days,
       ROUND(AVG(r.avg_review_score), 2) AS avg_review_score,
       COUNT(DISTINCT oc.order_id) AS orders
FROM order_category oc JOIN fact_orders o USING (order_id)
LEFT JOIN reviews_by_order r USING (order_id)
WHERE o.order_status = 'delivered' AND o.delivery_days IS NOT NULL
GROUP BY category ORDER BY avg_delivery_days DESC;
