# Lumen Shelf: Privacy Policy

*Last updated: 8 November 2026*

This policy explains what data Lumen Shelf uses, where it goes and how long it
is kept. Lumen Shelf is an app for ERPNext made by Lumen Solutions
("Lumen", "we"). Contact: support@lumen-solutions.co.

## The short version

- Lumen Shelf runs inside your own ERPNext site. Your stock, sales, prices,
  customers and suppliers stay there. Lumen does not receive them.
- Two optional features, **Trending products** and **Bundle ideas**, use
  Lumen's AI service. Both are off until an administrator switches them on
  and enters a key from Lumen. They send item names, item group names and
  your company's country, never quantities, prices, customers or the name of
  your business.
- Lumen does not sell your data and does not use it for advertising.

## What stays in your ERPNext site

Everything Lumen Shelf works out (sales speed, days left, reorder points,
transfer and purchase suggestions, stock health, forecasts, reports) is
computed and stored in your own site, from data already in ERPNext: items,
warehouses, stock levels, the stock ledger, invoices, purchase orders,
material requests, pricing rules and settings. None of it is sent to Lumen.

Who can see it inside your site is decided by your own ERPNext roles and user
permissions, and by the Shelf Manager and Shelf User roles the app adds.

## What the optional AI features send

These features work only after an administrator switches them on in Lumen
Shelf Settings and enters the service URL, API key and API secret that Lumen
issues. When they run (once a week, or when someone presses the button) your
site sends Lumen's AI service:

| Feature | What is sent |
|---|---|
| Trending products | Your company's country, the names of up to 12 of your item groups, and up to 40 item names in each of them. |
| Bundle ideas | Your company's country and, for up to 30 pairs of items, the two item names and their item groups. |
| Credit check | Nothing but the request itself, authenticated by your key. |

Nothing else is sent: no quantities, prices, costs, sales figures, customer or
supplier details, user names or the name of your company.

## How Lumen's AI service uses it

- **Purpose.** Only to answer your request: to find related searches and
  suggest products (Trending products), or to judge which pairs make a
  natural set and name them (Bundle ideas).
- **Service providers.** To do this the service sends search terms derived
  from your item groups to DataForSEO (Google Trends data), and the item and
  group names to Anthropic's Claude (an AI model). They process the data on
  Lumen's behalf to return an answer.
- **What Lumen keeps.**
  - Each request and its answer, for 90 days, then they are deleted.
  - Answers cached so the same question is not paid for twice: search
    results for 7 days and bundle answers for 30 days, deleted after at
    most 90 days. A cached answer holds item or search names only and can
    serve another shop that asks the same question.
  - A record of the cost of each request and the credit used by your key,
    kept for billing.
- **Who sees it.** Lumen staff who run the service, for support and billing.

## Billing

When you subscribe through the Frappe Cloud Marketplace, payment is handled
by Frappe Cloud under its own terms and privacy policy. Lumen does not
receive your card details.

## Your choices

- Leave the AI features off, or switch them off at any time in Lumen Shelf
  Settings. Nothing is sent while they are off.
- Ask us to delete the requests and answers linked to your key by writing to
  support@lumen-solutions.co. We will delete them within 30 days. The
  billing record of the amounts used may be kept as long as the law requires.
- Uninstalling Lumen Shelf removes its own settings, suggestions and reorder
  rows from your site. ERPNext documents you created with it (material
  requests, items, product bundles, item prices) are ordinary ERPNext
  documents and stay.

## Security

Requests to Lumen's AI service are authenticated with your API key and
secret. ERPNext stores the secret encrypted in your site. Use the service
over HTTPS.

## Changes

We will update this page when what is sent or kept changes, and record the
change in the user guide's change log.

## Contact

Lumen Solutions, https://lumen-solutions.co, support@lumen-solutions.co
