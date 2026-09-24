# Data Dictionary and Model Notes

All source files were inspected directly. Raw identifiers are strings. Timestamps are converted to Pandas datetimes by `python/data_cleaning.py`; postal prefixes are retained as strings so leading zeroes are not lost.

| Source table | Rows | Key / grain | Important fields | Quality notes |
|---|---:|---|---|---|
| `olist_orders_dataset.csv` | 99,441 | `order_id`, one order | `customer_id`, `order_status`, purchase/approval/carrier/delivered/estimated timestamps | 160 approval, 1,783 carrier, and 2,965 delivered timestamps missing; statuses include delivered, shipped, canceled, unavailable, invoiced, processing, created, approved. Purchase dates: 2016-09-04 to 2018-10-17. |
| `olist_customers_dataset.csv` | 99,441 | `customer_id` (unique order-customer record) | `customer_unique_id`, customer postal prefix, city, state | No missing cells. `customer_unique_id` repeats across order-specific customer IDs: 96,096 distinct IDs and 3,345 repeat rows. |
| `olist_order_items_dataset.csv` | 112,650 | (`order_id`, `order_item_id`), item line | `product_id`, `seller_id`, `price`, `freight_value`, `shipping_limit_date` | No missing cells; no duplicate full rows. `order_id` repeats by design; one order can include up to 21 item lines. Shipping limit dates include values as late as 2020-04-09, after the orders' purchase range, so retain and flag as source data rather than silently altering. |
| `olist_products_dataset.csv` | 32,951 | `product_id` | category name, product text lengths, photos, weight, dimensions | No duplicate product IDs. Category and three descriptive attributes missing for 610 products; weight/dimensions missing for 2. |
| `olist_sellers_dataset.csv` | 3,095 | `seller_id` | seller postal prefix, city, state | No missing cells. |
| `olist_order_payments_dataset.csv` | 103,886 | (`order_id`, `payment_sequential`), payment record | payment type, installments, payment value | No missing cells. 2,961 orders have multiple payment records; do not sum payments after joining to item lines. Types: credit card, boleto, voucher, debit card, not defined. |
| `olist_order_reviews_dataset.csv` | 99,224 | review record; `review_id` alone is not unique | `order_id`, score, comment fields, creation/answer timestamps | Comment title missing on 87,656 rows; message missing on 58,247. 814 repeated `review_id` records across different orders, not duplicate full rows. Scores range from 1 to 5. |
| `olist_geolocation_dataset.csv` | 1,000,163 | multiple coordinate observations per postal prefix | postal prefix, latitude/longitude, city/state | 261,831 exact duplicate rows; 19,015 distinct postal prefixes. 278 customer and 7 seller prefixes do not match. Processed into median coordinates per prefix for optional mapping. |
| `product_category_name_translation.csv` | 71 | `product_category_name` | English category name | No missing or duplicate keys. Two distinct non-null product categories have no translation; source names are retained. 610 products have no category at all. |

## Relationships

| From | To | Cardinality / join key | Notes |
|---|---|---|---|
| Orders | Customers | many orders to one `customer_id` | All 99,441 order customer IDs matched. `customer_unique_id` is the cross-order buyer identifier. |
| Order items | Orders | many item lines to one `order_id` | All 112,650 item rows matched an order. |
| Order items | Products | many item lines to one `product_id` | All item product IDs matched. |
| Order items | Sellers | many item lines to one `seller_id` | All item seller IDs matched. |
| Payments | Orders | many payment records to one `order_id` | All payments matched; keep at payment grain. |
| Reviews | Orders | many review records to one `order_id` | All review records matched; keep at review grain or aggregate reviews per order before order-level comparisons. |
| Products | Category translation | many products to zero/one category translation | Use left join so missing source categories are not dropped. |
| Customers | Geolocation | many customers to zero/one postal-prefix aggregate | Geolocation is pre-aggregated by prefix; 278 customer prefixes remain unmatched. |

## Type and cleaning rules

- Parse five order timestamps, item shipping-limit timestamp, and two review timestamps as datetimes. Keep missing times null.
- Keep all IDs, postal prefixes, state abbreviations, and category names as categorical/text dimensions, never as numeric measures.
- Use `price` as item product revenue and preserve `freight_value` as a separate measure. `payment_value` is a separate payment fact, not interchangeable with product revenue.
- Preserve multiple payment/review/item records; they represent valid table grain, not accidental duplicates.
- Use a left join for the English category lookup and retain the source category when no translation is available.
- Convert geolocation rows to one median coordinate per postal prefix before mapping; do not use an arbitrary single duplicate coordinate or join the raw million-row table to customers.

## Complete raw column inventory

Column types shown are pandas inference on the original CSV files; ID and postal-prefix fields are modeled as text in this project.

### `olist_customers_dataset.csv`

`customer_id`, `customer_unique_id`, `customer_zip_code_prefix`, `customer_city`, `customer_state`

### `olist_geolocation_dataset.csv`

`geolocation_zip_code_prefix`, `geolocation_lat`, `geolocation_lng`, `geolocation_city`, `geolocation_state`

### `olist_order_items_dataset.csv`

`order_id`, `order_item_id`, `product_id`, `seller_id`, `shipping_limit_date`, `price`, `freight_value`

### `olist_order_payments_dataset.csv`

`order_id`, `payment_sequential`, `payment_type`, `payment_installments`, `payment_value`

### `olist_order_reviews_dataset.csv`

`review_id`, `order_id`, `review_score`, `review_comment_title`, `review_comment_message`, `review_creation_date`, `review_answer_timestamp`

### `olist_orders_dataset.csv`

`order_id`, `customer_id`, `order_status`, `order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date`

### `olist_products_dataset.csv`

`product_id`, `product_category_name`, `product_name_lenght`, `product_description_lenght`, `product_photos_qty`, `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm`

### `olist_sellers_dataset.csv`

`seller_id`, `seller_zip_code_prefix`, `seller_city`, `seller_state`

### `product_category_name_translation.csv`

`product_category_name`, `product_category_name_english`

## Derived analytical tables

dim_date: one row per calendar date in the order purchase span; fields include date, year, quarter, month number/name, year-month, sort key.
dim_category: one row per display category.
fact_orders: one row per source order, with calculated purchase date/month, elapsed delivery days, nullable late flag, and customer_unique_id for time-filtered unique-buyer metrics.
fact_order_items: one row per order item, with English/fallback display category and separate item revenue and item-plus-freight fields.
fact_payments: one row per order-payment sequence.
fact_reviews: one row per review record.
fact_reviews_by_order: one row per order that has reviews, averaging its review scores and counting its review records.
fact_order_category: one row per order-category, aggregating product price, freight, item lines, and joining that order's delivery and review summary. Use this table only for category-attributed delivery/review questions; an order with multiple categories appears once in each relevant category.

