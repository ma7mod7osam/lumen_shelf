# Lumen Shelf: User Guide

*Applies to Lumen Shelf v0.2.0 (phase 1, with the smarter forecast).
This document is updated with every change.*

Lumen Shelf learns how fast each item sells in each outlet, works out how
many days are left on the shelf, and tells you what to transfer between
warehouses and what to buy, before anything runs out. It reads only what is
already in ERPNext. **Phase 1 is read only: it creates no document.**

It works on ERPNext v13, v14, v15 and v16, with or without LumenPOS. Sales are
counted from POS Invoices and Sales Invoices.

## 1. Installation and first day

Install the app and open **Lumen Shelf** in the desk. There is nothing to
fill in. On the first day it uses these defaults:

| Setting | Default |
|---|---|
| Restock from | Transfer first, then buy |
| Days of cover | 14 |
| Safety level | 95% |
| Supplier lead time | 7 days until learned |
| Transfer lead time | 2 days |
| Weeks of sales history | 8 |
| Suggest transfers between outlets | On |
| Days in stock needed before judging an outlet | 28 |
| Slow when stock lasts more than | 90 days |
| Overstock when stock lasts more than | 60 days |
| Adjust for seasons | On, calendar chosen automatically |
| Show rising and falling items | On, from 30% |
| Show lost sales | On |
| Plan purchases within a budget | On |
| Show forecast accuracy | On |

The supplier comes from the item's **Item Defaults** for the company, or else
from the item's most recent Purchase Order. The main warehouse is found on its
own (section 5). The settings page shows what was found.

## 2. The screens

All four are ERPNext reports, so they sort, filter, export to Excel and print
like any other report, in English or Arabic, light or dark.

### Running low (Shelf Running Low)

Per outlet, the items that will run out before a new delivery can arrive.

| Column | Meaning |
|---|---|
| On shelf | Stock in the warehouse (ERPNext's Bin) less what the tills sold that is not consolidated yet |
| Daily sales | Average units sold per day the item was in stock |
| Season effect | How much more (above 1) or less (below 1) sold last year in the weeks ahead. Blank when there is no season to learn from |
| Expected daily sales | Daily sales x season effect. The reorder point and the suggestion use this |
| Days left | On shelf divided by daily sales |
| On order | Open Purchase Orders and open Material Requests (purchase and transfer) |
| Reorder point | Below this, restock now |
| Suggested qty | Enough for the days of cover after the lead time, less what is on order |
| Source | By transfer, By purchase, Transfer and purchase, or Wait for main warehouse |
| Transfer from | The warehouse(s) the transfer comes from |
| Supplier, Buy in purchase unit | Who to buy from, rounded up to whole packs |
| Lead time (days) | How long the restock takes |
| Days in stock | How many days of history the figures rest on |

Days left (on the expected daily sales) shows red when it is shorter than the
lead time, amber otherwise.

**Budget.** Type an amount in the Budget filter. The purchases are put in
order: first what runs out within its lead time, then A items before B and C,
then what loses the most profit a day while it is missing. **In budget** marks
those that fit, with the running total. A purchase that does not fit is
skipped, and a cheaper one after it may still fit. **Purchase cost** is the
quantity x the item's last purchase rate, or its stock valuation rate if it has
never been bought.
Quantities that are zero are left blank.

### Transfer suggestions (Shelf Transfers)

Every suggested move: item, from, to, quantity, and why.

- **Running low there**: the receiving warehouse is short, and this covers it
  before anything is bought.
- **Sells faster there**: the item does not move in one outlet but sells in
  another, so the spare stock goes where it sells.

### Stock health (Shelf Stock Health)

Per outlet: the **ABC** ranking (A = the items making the first 80% of sales
value, B = the next 15%, C = the rest), and a status:

- **No sales**: in stock long enough, sold nothing.
- **Slow**: what is on the shelf lasts longer than the slow limit (90 days).
- **Overstock**: lasts longer than the overstock limit (60 days) and is more
  than the outlet needs. Excess qty and value show how much.
- **Too new**: not enough days in stock to judge yet.
- **OK**.

Days left shows **365+** when what is on the shelf lasts more than a year.

**Trend.** Rising or Falling compares the in-stock sales rate of the recent
half of the history window (the last 4 weeks) with the earlier half. It needs
at least 10 days in stock in each half and 10 units sold, and the change must
reach the setting (30% by default). Change (%) shows the figure.

**Lost sales** (outlets): the days an item was out of stock since it was first
on the shelf in the window, x its daily sales = Lost qty, x its average selling
price in the window = Lost sales. The total is at the top.

### Forecast accuracy (Shelf Forecast Accuracy)

What Lumen Shelf forecast 14 days ago for each outlet and item, against what
was sold since. Only items that stayed in stock all 14 days count, so an empty
shelf never reads as a bad forecast.

- **Accuracy** = 1 - (sum of the differences, all made positive) / units sold.
- **Forecast above (or below) sales by**: (forecast - sold) / sold, the
  overall lean of the forecast.
- **Plain average accuracy**: the same for a plain average (sales of the
  window / its days), so you can see what the smarter forecast gains.

## 3. How the numbers are worked out

**Daily sales.** The last 8 whole weeks, ending yesterday (today is not over).
The most recent week counts 8 times, the oldest once. A day the item was out of
stock in that warehouse is left out, so an empty shelf never reads as no
demand. A day counts as in stock when the Stock Ledger shows stock at its start
or at any point during it, or when something sold that day. Returns reduce
sales. Parts of a product bundle count as sales of the parts.

POS sales are counted once: from the POS Invoice. The Sales Invoice ERPNext
makes when a shift closes (marked as consolidated) is not counted again.

**Lead time.** Learned per supplier: the days from the Purchase Order date to
the Purchase Receipt date, the middle value of the last 10 receipts. Until a
supplier has one, the item's own Lead Time in Days is used if filled, else the
default (7 days). A transfer takes the transfer lead time (2 days).

**Safety stock** grows with how much daily sales swing and with the lead time.
An item that sells exactly the same every day needs none.

**Reorder point** = daily sales x lead time + safety stock.

**Suggested quantity** = reorder point + daily sales x days of cover, less what
is on the shelf and on order, plus what is promised to Sales Orders. A purchase
is rounded up to the item's purchase unit (for example boxes of 6) and to its
minimum order quantity. A transfer is rounded down to whole units.

**Seasons.** Lumen Shelf looks at the same item a year ago: its sales over the
weeks ahead (lead time + days of cover, in whole weeks, 1 to 13) against its
sales over the weeks of the history window. If last year sold 3 times as much
in the weeks ahead, the season effect is 3. It is kept between 0.25 and 4.

- An item needs 20 units sold last year in those window weeks for its own
  season. Otherwise it takes its item group's (50 units needed). Otherwise
  there is no season effect.
- **Seasons follow**: Gregorian looks back 364 days (the same weekday), for
  dates that repeat every year. Hijri looks back 354 days (one Hijri year), for
  Ramadan and Eid. **Choose automatically** (default) tries both on the
  company's last 8 weeks, 2 weeks at a time, from the 8 weeks before each, and
  uses the one that came closest, if it beats leaving seasons out. The report
  says which one is used.
- Nothing is assumed about the country or religion: the shop's own history
  decides. A shop with less than a year of history has no season effect yet.

Seasons change the expected daily sales, the reorder point, the suggestion and
days left. Slow, overstock and the "sells faster there" transfers stay on the
history, what really sold.

## 4. Where a shortage is filled from

Settings, **Restock from**:

| Choice | Order |
|---|---|
| Transfer first, then buy (default) | Main warehouse, then other outlets' surplus, then buy |
| Buy from supplier | Other outlets' surplus, then buy |
| Transfer from main warehouse | Main warehouse, then other outlets' surplus. What the main warehouse lacks shows as Wait for main warehouse, and the main warehouse buys it |

**Surplus in one outlet always covers a shortage in another before anything is
bought**, unless "Suggest transfers between outlets" is off. The guards:

- An outlet gives stock away only after it has had the item on the shelf for
  28 days (setting), so a new item is never judged too early.
- Only what is beyond that outlet's own cover moves. It keeps enough for itself.
- "Sells faster there" needs the receiving outlet to sell at least twice as
  fast, and it receives no more than it can sell within its own cover.

## 5. The main warehouse

Named in the settings (Warehouse roles), or else found on its own: the
warehouse that sent the most Material Transfers to the company's other
warehouses in the last 90 days. Its demand is its own sales plus what it sends
to outlets, and it buys what it is left short of. Warehouses of type Transit,
rejected warehouses, and warehouses marked **Leave out** are not used.

## 6. Settings

**Lumen Shelf Settings**. Every field is optional.

- **Enabled** switches the whole app off for everyone.
- **Suggest transfers between outlets**, **Show stock health**, **Adjust for
  seasons**, **Show rising and falling items**, **Show lost sales**, **Plan
  purchases within a budget** and **Show forecast accuracy** switch those
  parts off.
- **Warehouse roles** (optional): name the main warehouse per company, or leave
  a warehouse out.

## 7. Who sees what

- Roles that see the lists: **Shelf Manager** (also edits the settings),
  **Shelf User**, Stock Manager, Purchase Manager, System Manager.
- The reports also need ERPNext's own stock access (read on Bin), as every
  stock report does. Give a Shelf User the Stock User role as well.
- **User Permissions** on Warehouse limit a person to their outlets: they see
  only those outlets' lists, and only the transfers that touch them. User
  Permissions on Company work the same way.
- The checks are on the server, not only in the screen.

## 8. LumenPOS and other apps

Lumen Shelf works on its own. When LumenPOS is installed, the till will show
the manager the running-low list (built by LumenPOS against the contract
below). Another app can let its own roles see the lists by adding, in its
hooks.py:

```python
lumen_shelf_viewer_roles = ["LumenPOS Manager"]
```

The contract, version 1 (`lumen_shelf.api`):

- `state()`: app, version, contract, enabled, can_view. Never fails.
- `running_low(company, warehouse)` and `transfers(company, warehouse)`:
  `{status: "ok", contract, company, as_of, window, main_warehouse, rows}`, or
  `{status: "disabled" | "forbidden" | "error", message}`. The row fields are
  listed in `lumen_shelf/api.py`.

## 9. Phases

1. **Now**: forecast and lists, read only.
2. **Next**: one button creates ERPNext Material Requests from the suggestions,
   grouped by supplier or source warehouse. ERPNext's own button turns them
   into Purchase Orders.
3. **Later**: an automatic mode with alerts that keeps ERPNext's own Item
   Reorder levels up to date and lets ERPNext's own automatic Material Requests
   run. The default stays "suggest, the shop approves".

## 10. Changelog

### 0.2.0 (2026-10-31)

- Seasons learned from last year's sales, on the Gregorian or the Hijri
  calendar, chosen automatically from what predicted the last 8 weeks best.
  New columns Season effect and Expected daily sales.
- Rising and falling items, with the change in percent.
- Sales lost while items were out of stock, per outlet, in money.
- A budget filter on Running low: purchases ranked by urgency and value, and
  which fit. Purchase cost on every purchase.
- New report Forecast accuracy: the forecast of 14 days ago against what sold,
  next to a plain average.
- A switch for each in the settings.

### 0.1.0 (2026-10-29)

- First version, phase 1, read only.
- Named Lumen Shelf by the owner (called Lumen Restock while it was built).
- Proprietary licence (closed source), see license.txt.
- Daily sales per item and outlet, weighted to recent weeks, days out of stock
  left out, from POS Invoices and Sales Invoices without double counting.
- Days left, lead times learned per supplier, safety stock, reorder point,
  suggested quantity rounded to the purchase pack and minimum order.
- Transfer suggestions: main warehouse first, then other outlets' surplus,
  then buy. Stock that does not sell in one outlet moves to where it sells.
- Stock health: ABC ranking, slow, no sales, overstock with its value.
- Three reports, a workspace, settings with switches, roles, Warehouse and
  Company User Permissions, English and Arabic.
- Contract 1 for LumenPOS and other apps.
- Works on ERPNext v13, v14, v15 and v16.
