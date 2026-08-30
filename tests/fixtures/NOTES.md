# Synthetic fixture notes

The JSON files in this directory are minimal, fabricated payloads. They retain
only the field shapes needed to test normalization, tier classification,
pricing, and schema validation. They are not recorded vendor responses.

- `basic_page1.json` models two Basic records, including an intentionally
  unordered price-tier list.
- `search_stm32.json` models a Promotional Extended record and an Extended
  alternative.

When the upstream schema changes, reproduce the behavior with the smallest
synthetic fixture possible. Do not commit raw API responses, cookies, request
headers, account data, or vendor datasets.
