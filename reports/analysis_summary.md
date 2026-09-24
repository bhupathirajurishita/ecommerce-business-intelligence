# Verified Olist analysis snapshot

Calculated from the supplied files by `python/create_analysis_reports.py`. These are descriptive results for the dataset snapshot, not current marketplace performance.

## Headline results

- Product-price revenue: **R$ 13,221,498.11** (sum of item `price`; excludes freight and is not payment value).
- Delivered orders: **96,478**.
- Average product-price order value: **R$ 137.04** (delivered product revenue / delivered orders).
- Average delivery duration: **12.56 days** across 96,470 delivered orders with valid purchase/delivery timestamps.
- Late-delivery share: **8.1%** among delivered orders whose late/on-time flag is defined.
- Average order-level review score: **4.09 / 5** across 98,673 orders with review records of any status (multiple reviews averaged within order first).
- Repeat identified buyers: **2,997 / 96,096 (3.1%)** have more than one order, using `customer_unique_id` and all statuses.

## Largest category and state by delivered product-price revenue

- Category: **Health Beauty** — R$ 1,233,131.72.
- Customer state: **SP** — R$ 5,067,633.16.

## Interpretation notes

- Category and state values are derived from item lines linked to delivered orders; multi-item orders contribute the price of each line.
- The delivery rate excludes delivered orders with missing timestamps or missing comparison dates as appropriate.
- Payment value is separate from product-price revenue; a payment can be split across payment records/methods.
- Repeat-buyer share is based on stable `customer_unique_id`, not the order-specific `customer_id`.

## Exports

See the accompanying CSVs in this folder for monthly trend, category, product, state, payment, review, and delivery breakdowns.
