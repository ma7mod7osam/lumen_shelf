# Lumen Shelf

Smart restocking for ERPNext v13 to v16, by
[Lumen Solutions](https://lumen-solutions.co).

Lumen Shelf learns how fast each item sells in each outlet, works out how
many days are left on the shelf, and tells you what to transfer between
warehouses and what to buy, before anything runs out. Everything is in one
screen at `/shelf`, in English and Arabic.

## What it does

- **Today**: one page with what needs doing now, written as plain sentences:
  what is running low, what to move between outlets, what may expire and
  what is not selling.
- **Restocking**: sales speed per item and outlet, days left, reorder point
  and a suggested quantity rounded to the purchase pack. One button turns
  the suggestions into ERPNext Material Requests, grouped by supplier or by
  sending warehouse.
- **Transfers first**: stock that sells in one outlet and not in another moves
  to where it sells before anything is bought.
- **Smarter forecast**: seasons learned from your own sales (Gregorian or
  Hijri calendar), promotions, rising and falling items, expiry, new items
  judged from similar ones, and a report of how accurate the forecast was.
- **Automatic mode** (off by default): keeps ERPNext's own reorder levels up
  to date every night, and ERPNext raises the requests.
- **Ideas**: items that sell elsewhere but are missing from an outlet, items
  bought together, and, with Lumen's optional AI service, trending products
  and ready to sell bundles.

It reads what is already in ERPNext (Bin, Stock Ledger, POS and Sales
Invoices) and works on any ERPNext site with stock, with or without a
separate point of sale app. Every feature has its own switch, and access
follows ERPNext roles and user permissions.

## Install

```bash
bench get-app https://github.com/ma7mod7osam/lumen_shelf
bench --site your-site install-app lumen_shelf
```

Then open `/shelf` and, as a System Manager or Shelf Manager, check Lumen
Shelf Settings. It works from day one on its defaults.

## Documentation

- [User guide and change log](docs/user-guide.md)
- [Privacy Policy](docs/privacy-policy.md)
- [Terms of Service](docs/terms-of-service.md)

## Support

support@lumen-solutions.co

## Licence

Copyright (C) 2026 Lumen Solutions.

Lumen Shelf is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, version 3. It is distributed without any warranty. See
[license.txt](license.txt).

Lumen's AI service, used by the optional Trending products and Bundle ideas
features, is a separate service run by Lumen and is not part of this
repository.
