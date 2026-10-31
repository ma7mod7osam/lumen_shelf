# Lumen Shelf: User Guide

*Applies to Lumen Shelf v0.7.0 (promotions).
This document is updated with every change.*

Lumen Shelf learns how fast each item sells in each outlet, works out how
many days are left on the shelf, and tells you what to transfer between
warehouses and what to buy, before anything runs out. It reads only what is
already in ERPNext. It creates a document only when someone presses
**Create material requests**: then it makes ERPNext Material Requests, and
nothing else. In **automatic mode** (off by default) it keeps ERPNext's own
reorder levels up to date every night, and ERPNext raises the requests.

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
| Forecast by demand pattern | On |
| Forecast new items from similar ones | On |
| Watch expiry dates | On |
| Suggest what to do with stock that does not sell | On |
| Show items bought together | On |
| Show assortment gaps | On |
| Create material requests from the suggestions | On |
| Submit the requests | On |
| Keep ERPNext's reorder levels up to date (automatic mode) | Off |
| Daily alert to Shelf Managers | On |
| Learn from promotions | On |

The supplier comes from the item's **Item Defaults** for the company, or else
from the item's most recent Purchase Order. The main warehouse is found on its
own (section 5). The settings page shows what was found.

## 2. The screens

All seven are ERPNext reports, so they sort, filter, export to Excel and print
like any other report, in English or Arabic, light or dark.

### Running low (Shelf Running Low)

Per outlet, the items that will run out before a new delivery can arrive.

| Column | Meaning |
|---|---|
| On shelf | Stock in the warehouse (ERPNext's Bin) less what the tills sold that is not consolidated yet |
| Daily sales | Average units sold per day the item was in stock |
| Season effect | How much more (above 1) or less (below 1) sold last year in the weeks ahead. Blank when there is no season to learn from |
| Expected daily sales | The base x season effect. The reorder point and the suggestion use this |
| Promotion effect | How much a promotion planned within the lead time and cover raises the expected sales. Blank when there is none |
| Based on | Where the base comes from: Sales history, Sales history with promotions left out, Demand pattern, or Similar items (brand or group) |
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

**Create material requests** (button at the top). It turns what the screen
shows, with its filters, into ERPNext Material Requests. See section 2a.

### Transfer suggestions (Shelf Transfers)

Every suggested move: item, from, to, quantity, and why.

- **Running low there**: the receiving warehouse is short, and this covers it
  before anything is bought.
- **Sells faster there**: the item does not move in one outlet but sells in
  another, so the spare stock goes where it sells.

The same **Create material requests** button makes one transfer request per
sending warehouse for the moves shown. See section 2a.

### 2a. Create material requests

On **Running low** and **Transfer suggestions**, the button at the top shows
what it will create and asks before it does:

- **Purchases**: one Material Request (type Purchase) per supplier, a line per
  item and warehouse, in the purchase unit (whole packs). Items with no known
  supplier go on one request, "supplier to choose". In ERPNext, open the
  request and use **Create > Purchase Order**.
- **Transfers**: one Material Request (type Material Transfer) per sending
  warehouse, a line per item and receiving warehouse. In ERPNext, open the
  request and use **Create > Transfer Material**.
- **Required by** on each line: today plus the lead time (purchases) or the
  transfer lead time (transfers).
- It asks for what the screen shows: with a warehouse, item group or source
  filter, only those. With a **Budget** on Running low, only the purchases that
  fit it. Transfers do not spend the budget.
- **Nothing is asked twice.** A submitted request counts in ERPNext as on
  order at the receiving warehouse, so the suggestion goes away. At the
  sending warehouse, stock asked for by a submitted transfer request and not
  yet moved is no longer counted as spare, so it is never promised twice.
  Quantities already on a draft request are taken off.
- The requests are saved with ERPNext's own checks. The quantities are worked
  out again from fresh figures when you confirm. If one request fails, none is
  kept.
- **Submit the requests** (setting, on by default). Off: they are saved as
  drafts for someone to check and submit. ERPNext counts a draft as nothing
  until it is submitted.

Who may press it: Shelf Manager, Stock Manager, Purchase Manager, System
Manager, and only if ERPNext also lets them create (and submit) a Material
Request. Shelf User does not see the button. A person limited to some
warehouses gets only the lines whose every warehouse they may see.

### 2b. Automatic mode

Off by default: the shop approves every suggestion. Switched on in **Lumen
Shelf Settings > Automatic mode**:

- **Every night at 00:15** Lumen Shelf sets, for each item and warehouse, the
  **reorder level** and **reorder quantity** in ERPNext's own table (Item >
  Inventory > Reorder Levels):
  - reorder level = the reorder point (sales during the lead time + safety)
  - reorder quantity = enough for the days of cover, in whole packs and at
    least the minimum order (purchases) or whole units (transfers)
  - type = Transfer for an outlet that restocks from the main warehouse,
    otherwise Purchase
- **At 00:45 ERPNext's own job** raises the Material Requests: when ERPNext's
  projected quantity is at or below the level, it asks for the reorder
  quantity, or more if the stock fell further. Lumen Shelf never creates a
  request in this mode. Transfer requests from ERPNext name only the receiving
  warehouse: the sending one is chosen when the transfer is made.
- Only items with enough history (or a new item forecast from similar ones)
  get a level. A level no longer needed is removed.
- **A level you set yourself is kept.** Lumen Shelf marks its own rows (**Set
  by Lumen Shelf**, read only) and never touches the others. Where you set a
  level for an item and warehouse, it sets none. To take one over, delete the
  Lumen Shelf row and add your own.
- Switching automatic mode on also switches on ERPNext's own automatic
  material requests (Stock Settings). Switching automatic mode off, or the
  whole app off, removes every level Lumen Shelf set.
- **Update reorder levels now** (button) does tonight's update right away.
  **Last update** and **Result of the last update** show what it did.
- **Daily alert to Shelf Managers** (on by default): a bell notification after
  each update, with what changed and how many items are running low. ERPNext
  can also email when it raises requests (Stock Settings, Notify by Email on
  Creation of Automatic Material Request).

Who may press the button: Shelf Manager or System Manager, with ERPNext's own
permission to change items.

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

**Demand pattern** (Smooth, Erratic, Intermittent, Lumpy) and **Suggested
action** for stock that does not sell, see section 3. **Will expire unsold**
and **Expiry risk value**: stock in batches that will pass its expiry date
before it sells, the first to expire selling first, at the expected daily
sales. The total is at the top.

### Bought together (Shelf Bought Together)

Pairs of items that were on the same invoice in the history window, at least
3 times. **Confidence**: of the invoices with the item, the share that also had
the other one. **Lift**: how many times more often than chance (above 1, they
go together).

### Assortment gaps (Shelf Assortment Gaps)

Items that sell at least 0.5 a day in one outlet that another outlet did not
stock, sell or order at all in the whole history window. Only warehouses that
sold something count as outlets, so store rooms are never listed, and never
the main warehouse. **Starting qty**: the typical (middle) daily sales where it
sells x (lead time + days of cover).

### Promotions (Shelf Promotions)

Per outlet and item: **Promotion days** (days it sold mostly at a discount),
**Daily sales, normal days** and **on promotion**, **Lift (times)**, and the
**Next promotion** planned within the lead time and cover: where it is set
(ERPNext pricing rule or LumenPOS promotion), when it starts and ends, its
days ahead, its **Promotion effect** and the **Extra qty planned** for it.

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

**The base.** Usually the daily sales above. Two exceptions:

- **Demand pattern.** An item that sells now and then (a sale less than about
  every 1.3 days in stock) is Intermittent, or Lumpy if the sizes of its sales
  swing a lot. Its base is worked out from the size of its sales and the gaps
  between them, each smoothed (Croston's method with the Syntetos-Boylan
  correction), instead of an average that would swing up after every sale.
  It needs 2 days with a sale.
- **New items.** An item first on the shelf in the last 14 days of the window
  takes the typical (middle) daily sales of items of the same brand and item
  group in the same warehouse that have been in stock 28 days or more, if
  there are 3 of them. Otherwise items of the same group (3 or more).

**Promotions.** A promotion day for an item in an outlet is a day on which at
least half of what it sold went at 5% or more under the line's price list
rate (an ERPNext pricing rule, a LumenPOS promotion or a manual discount, all
kept on the invoice line).

- Those days are left out of the base (and of how much sales swing), so a
  past promotion does not make the next order too big. It needs 14 normal
  days in stock.
- **Lift** = average sales on promotion days / average on the other days in
  stock. It needs 3 promotion days and 14 normal days.
- A **planned promotion** that covers the item in that outlet raises the
  expected sales over the lead time and cover: x (1 + (lift - 1) x promotion
  days in that period / days in that period). The lift is used up to 5 times,
  and never lowers anything. Without a measured lift, nothing changes, but
  the promotion is still listed.
- Planned promotions read: ERPNext selling **Pricing Rules** with an end date
  (on an item, an item group and the groups under it, or a brand, for the
  company, and for one warehouse when the rule names it), and, when LumenPOS
  is installed, its active **promotions** with an end date and no coupon
  (their items, groups, brands, exclusions, POS profiles' warehouses and
  weekdays). A rule with no end date is a standing price: it is already in
  the sales history.

**Shelf life.** An item with a Shelf Life In Days never gets more cover than
its shelf life less the lead time (at least 1 day), so nothing is bought to
expire on the shelf.

**Stock that does not sell** (No sales, Slow, Overstock) gets a suggested
action, the first that applies:

1. **Move to** an outlet where it sells faster (the transfer is in Transfer
   suggestions).
2. **Return to** the supplier, if it came in on a Purchase Receipt in the last
   60 days.
3. **Sell together with** an item it is bought with (Bought together) that
   sells well in the same warehouse.
4. **Discount.**

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
  purchases within a budget**, **Show forecast accuracy**, **Forecast by demand
  pattern**, **Forecast new items from similar ones**, **Watch expiry dates**,
  **Suggest what to do with stock that does not sell**, **Show items bought
  together**, **Show assortment gaps**, **Learn from promotions** and **Create
  material requests from the suggestions** switch those parts off.
- **Submit the requests**: on, the button submits the requests. Off, it saves
  them as drafts.
- **Keep ERPNext's reorder levels up to date** (automatic mode, off by
  default) and **Daily alert to Shelf Managers**, see section 2b.
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
- **Create material requests**: Shelf Manager, Stock Manager, Purchase
  Manager, System Manager, with ERPNext's own permission to create (and
  submit) a Material Request. Not Shelf User.
- The checks are on the server, not only in the screen.

## 8. LumenPOS and other apps

Lumen Shelf works on its own. When LumenPOS is installed, the till will show
the manager the running-low list (built by LumenPOS against the contract
below). Another app can let its own roles see the lists by adding, in its
hooks.py:

```python
lumen_shelf_viewer_roles = ["LumenPOS Manager"]
```

The till can also show a **Create material requests** button (contract 2).
A role named by another app in its hooks.py may press it, with ERPNext's own
Material Request permission on top:

```python
lumen_shelf_request_roles = ["LumenPOS Manager"]
```

The contract, version 2 (`lumen_shelf.api`):

- `state()`: app, version, contract, enabled, can_view, can_request,
  submit_requests. Never fails.
- `running_low(company, warehouse)` and `transfers(company, warehouse)`:
  `{status: "ok", contract, company, as_of, window, main_warehouse, rows}`, or
  `{status: "disabled" | "forbidden" | "error", message}`. The row fields are
  listed in `lumen_shelf/api.py`.
- `preview_requests(company, warehouse, scope)`: the Material Requests the
  button would make now, for one outlet (`scope` "running_low", its
  shortages) or its moves (`scope` "transfers").
- `create_requests(company, warehouse, scope)`: makes them, all or nothing,
  with the same rules as the desk button (section 2a).

## 9. Phases

1. **Done**: forecast and lists, read only.
2. **Done**: one button creates ERPNext Material Requests from the suggestions,
   grouped by supplier or source warehouse. ERPNext's own button turns them
   into Purchase Orders.
3. **Now**: an automatic mode with alerts that keeps ERPNext's own Item
   Reorder levels up to date and lets ERPNext's own automatic Material Requests
   run. The default stays "suggest, the shop approves".

## 10. Changelog

### 0.7.0 (2026-10-31)

- Promotions: days sold mostly at a discount are left out of the normal
  sales, the lift of each item is measured, and a promotion planned in ERPNext
  (a pricing rule with an end date) or in LumenPOS raises the suggestion
  before it starts.
- New report Promotions. Running low shows the promotion effect.
- Switch **Learn from promotions**.

### 0.6.0 (2026-10-31)

- API contract 2 for the till: `preview_requests` and `create_requests` make
  the material requests for one outlet, all or nothing. `state()` tells the
  till whether to show the button (`can_request`).
- Hook `lumen_shelf_request_roles`: another app names roles that may create
  requests (LumenPOS: its manager role).

### 0.5.0 (2026-10-31)

- Phase 3, automatic mode (off by default): every night Lumen Shelf sets
  ERPNext's own reorder level and quantity per item and warehouse from its
  forecast, and ERPNext's own job raises the material requests.
- Levels the shop set itself are kept. Switching off removes the levels
  Lumen Shelf set. Turning it on switches on ERPNext's automatic requests.
- **Update reorder levels now** button, last update and its result on the
  settings page, and a daily bell alert to Shelf Managers.

### 0.4.0 (2026-10-31)

- Phase 2: a **Create material requests** button on Running low and Transfer
  suggestions. Purchases one request per supplier, transfers one per sending
  warehouse, in the purchase unit, with the required-by date from the lead
  time. It follows the screen's filters and the budget.
- Stock asked for by a submitted transfer request is no longer counted as
  spare at the sending warehouse. Draft requests are taken off what the button
  asks for.
- Settings: **Create material requests from the suggestions** and **Submit the
  requests**.

### 0.3.0 (2026-10-31)

- Demand patterns: items that sell now and then are forecast from the size of
  their sales and the gaps between them.
- New items take the typical sales of similar items (same brand and group, or
  same group) in the same warehouse.
- Shelf life caps the cover. Batches that will expire before they sell, in
  quantity and value.
- A suggested action for stock that does not sell: move, return, sell
  together, or discount.
- New report Bought together.
- New report Assortment gaps.
- A switch for each.

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
