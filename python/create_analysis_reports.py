"""Export business summaries from the Olist SQLite model without fan-out joins."""
from pathlib import Path
import sqlite3
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'data'/'processed'/'olist_analytics.db'; OUT=ROOT/'reports'; OUT.mkdir(exist_ok=True)
queries={
'monthly_sales':"""SELECT strftime('%Y-%m',o.order_purchase_timestamp) month, ROUND(SUM(i.price),2) product_revenue, COUNT(DISTINCT o.order_id) orders FROM fact_orders o JOIN fact_order_items i USING(order_id) WHERE o.order_status='delivered' GROUP BY month ORDER BY month""",
'category_sales':"""SELECT i.category_english category, ROUND(SUM(i.price),2) product_revenue, COUNT(DISTINCT i.order_id) orders, COUNT(*) item_lines FROM fact_order_items i JOIN fact_orders o USING(order_id) WHERE o.order_status='delivered' GROUP BY category ORDER BY product_revenue DESC""",
'top_products':"""SELECT p.product_id,p.category_english category,ROUND(SUM(i.price),2) product_revenue,COUNT(DISTINCT i.order_id) orders,COUNT(*) item_lines FROM fact_order_items i JOIN dim_products p USING(product_id) JOIN fact_orders o USING(order_id) WHERE o.order_status='delivered' GROUP BY p.product_id,p.category_english ORDER BY product_revenue DESC LIMIT 20""",
'state_sales':"""SELECT c.customer_state state,ROUND(SUM(i.price),2) product_revenue,COUNT(DISTINCT o.order_id) orders,COUNT(DISTINCT c.customer_unique_id) customers FROM fact_orders o JOIN dim_customers c USING(customer_id) JOIN fact_order_items i USING(order_id) WHERE o.order_status='delivered' GROUP BY state ORDER BY product_revenue DESC""",
'payment_methods':"""SELECT payment_type,COUNT(*) payment_records,COUNT(DISTINCT order_id) orders_using_method,ROUND(SUM(payment_value),2) recorded_payment_value,ROUND(AVG(payment_installments),2) avg_installments FROM fact_payments GROUP BY payment_type ORDER BY recorded_payment_value DESC""",
'review_distribution':"""WITH per_order AS (SELECT order_id,AVG(review_score) score FROM fact_reviews GROUP BY order_id) SELECT score review_score,COUNT(*) orders FROM per_order GROUP BY score ORDER BY score""",
'delivery_review':"""WITH r AS (SELECT order_id,AVG(review_score) score FROM fact_reviews GROUP BY order_id) SELECT CASE WHEN o.delivery_late=1 THEN 'Late' WHEN o.delivery_late=0 THEN 'On time or early' ELSE 'Unknown / not delivered' END delivery_result, ROUND(AVG(r.score),2) avg_review_score, COUNT(*) orders FROM fact_orders o LEFT JOIN r USING(order_id) GROUP BY delivery_result""",
'category_delivery':"""WITH oc AS (SELECT order_id,category_english,SUM(price) cat_revenue FROM fact_order_items GROUP BY order_id,category_english) SELECT oc.category_english category,ROUND(AVG(o.delivery_days),2) avg_delivery_days,ROUND(AVG(r.score),2) avg_review_score,COUNT(DISTINCT oc.order_id) orders FROM oc JOIN fact_orders o USING(order_id) LEFT JOIN (SELECT order_id,AVG(review_score) score FROM fact_reviews GROUP BY order_id) r USING(order_id) WHERE o.order_status='delivered' AND o.delivery_days IS NOT NULL GROUP BY category ORDER BY avg_delivery_days DESC""",
'customer_metrics':"""WITH item_totals AS (SELECT order_id,SUM(price) price FROM fact_order_items GROUP BY order_id), co AS (SELECT o.order_id,o.customer_unique_id,o.order_status,COALESCE(i.price,0) price FROM fact_orders o LEFT JOIN item_totals i USING(order_id)) SELECT customer_unique_id,COUNT(DISTINCT order_id) orders,SUM(CASE WHEN order_status='delivered' THEN 1 ELSE 0 END) delivered_orders,ROUND(SUM(CASE WHEN order_status='delivered' THEN price ELSE 0 END),2) delivered_product_revenue,CASE WHEN COUNT(DISTINCT order_id)>1 THEN 'Repeat' ELSE 'One-time' END customer_type FROM co GROUP BY customer_unique_id ORDER BY delivered_product_revenue DESC""",
}
with sqlite3.connect(DB) as con:
    tables={name:pd.read_sql_query(sql,con) for name,sql in queries.items()}
    orders=pd.read_sql_query('SELECT * FROM fact_orders',con)
    customer=pd.read_sql_query('SELECT customer_id,customer_unique_id FROM dim_customers',con)
for n,df in tables.items(): df.to_csv(OUT/f'{n}.csv',index=False)
tables['state_sales'].to_csv(OUT/'region_sales.csv',index=False)
orders['delivery_days']=pd.to_numeric(orders.delivery_days,errors='coerce')
deliv=orders[(orders.order_status=='delivered') & orders.delivery_days.notna()]
item_revenue=tables['category_sales'].product_revenue.sum()
revenue_share=tables['category_sales'].iloc[0]
late=deliv.delivery_late.astype('boolean')
late_rate=float(late.fillna(False).sum()/late.notna().sum()) if late.notna().sum() else float('nan')
rs=tables['review_distribution']; total_reviews=rs.orders.sum(); avg_score=(rs.review_score*rs.orders).sum()/total_reviews
joined=orders[['order_id','customer_id','order_status']].merge(customer,on='customer_id',how='left')
uniq=joined.drop_duplicates('order_id').groupby('customer_unique_id').order_id.nunique()
repeat=int((uniq>1).sum()); cust_count=int(uniq.size)
pay=tables['payment_methods'].iloc[0]
month=tables['monthly_sales']
lines=["# Verified Olist analysis snapshot","", "Calculated from the supplied files by `python/create_analysis_reports.py`. These are descriptive results for the dataset snapshot, not current marketplace performance.","", "## Headline results", "",f"- Product-price revenue: **R$ {item_revenue:,.2f}** (sum of item `price`; excludes freight and is not payment value).",f"- Delivered orders: **{orders.loc[orders.order_status.eq('delivered'),'order_id'].nunique():,}**.",f"- Average product-price order value: **R$ {item_revenue / orders.loc[orders.order_status.eq('delivered'),'order_id'].nunique():,.2f}** (delivered product revenue / delivered orders).",f"- Average delivery duration: **{deliv.delivery_days.mean():.2f} days** across {len(deliv):,} delivered orders with valid purchase/delivery timestamps.",f"- Late-delivery share: **{late_rate:.1%}** among delivered orders whose late/on-time flag is defined.",f"- Average order-level review score: **{avg_score:.2f} / 5** across {total_reviews:,} orders with review records of any status (multiple reviews averaged within order first).",f"- Repeat identified buyers: **{repeat:,} / {cust_count:,} ({repeat/cust_count:.1%})** have more than one order, using `customer_unique_id` and all statuses.","", "## Largest category and state by delivered product-price revenue", "",f"- Category: **{revenue_share['category']}** — R$ {revenue_share['product_revenue']:,.2f}.",f"- Customer state: **{tables['state_sales'].iloc[0]['state']}** — R$ {tables['state_sales'].iloc[0]['product_revenue']:,.2f}.","", "## Interpretation notes", "", "- Category and state values are derived from item lines linked to delivered orders; multi-item orders contribute the price of each line.","- The delivery rate excludes delivered orders with missing timestamps or missing comparison dates as appropriate.","- Payment value is separate from product-price revenue; a payment can be split across payment records/methods.","- Repeat-buyer share is based on stable `customer_unique_id`, not the order-specific `customer_id`.","", "## Exports", "", "See the accompanying CSVs in this folder for monthly trend, category, product, state, payment, review, and delivery breakdowns."]
(OUT/'analysis_summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(OUT/'summary.txt').write_text('\n'.join(line.replace('**','').replace('# ','') for line in lines)+'\n',encoding='utf-8')
print('\n'.join(lines[:17]))



