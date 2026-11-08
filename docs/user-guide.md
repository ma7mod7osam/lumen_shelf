# Lumen Shelf: User Guide

*Applies to Lumen Shelf v0.13.0 (bundle ideas).
This document is updated with every change.*

Lumen Shelf learns how fast each item sells in each outlet, works out how
many days are left on the shelf, and tells you what to transfer between
warehouses and what to buy, before anything runs out. It reads only what is
already in ERPNext. It creates a document only when someone presses
**Create material requests** (ERPNext Material Requests) or **Create bundle**
(an ERPNext Product Bundle, its item and its price), and nothing else. In **automatic mode** (off by default) it keeps ERPNext's own
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
| Respect shelf capacity | On |
| Suggest trending products | Off (needs a key from Lumen) |

The supplier comes from the item's **Item Defaults** for the company, or else
from the item's most recent Purchase Order. The main warehouse is found on its
own (section 5). The settings page shows what was found.

## 2. The screens

### The Lumen Shelf app (/shelf)

Lumen Shelf is one app of its own at **/shelf** on the site, like LumenPOS at
/pos. The Lumen Shelf icon on the apps screen, the Lumen Shelf entry in the
side menu and its first shortcut all open it. Everything is inside it, with
its own menu (a bar at the bottom on a phone):

- **Today**: what needs doing today (below).
- **Running low**, **Transfer suggestions**, **Stock health**, **Promotions**
  and **Forecast accuracy**: the detail screens, each with its own filters, a
  search box, sorting by any column and **Save for Excel**.
- **Product ideas**: trending in the market, missing in a branch, often bought
  together, one tab each.
- **Settings**: every setting, for a Shelf Manager or System Manager. A saved
  API secret is never shown, typing a new one replaces it.

The company is chosen at the top. The app follows the person's language
(Arabic right to left) and light or dark theme, and the moon button switches
the theme. **Back to ERPNext** returns to the desk. A screen whose switch is
off is not in the menu. The figures, filters and permissions are exactly the
ERPNext reports' (the app shows their rows), so a person sees in the app what
they may see in the reports and nothing more.

### Today

The first screen of the app has everything that needs doing today. Choose,
if you like, one branch or warehouse.

The first time it opens, a short note says what Lumen Shelf does in three
steps. **Got it** hides it on that device, **How it works** brings it back.
Under the title one line says what the numbers are based on (the last weeks
of sales up to yesterday, and the stock now). **How we calculated this** shows
the full detail: dates, main warehouse, where restocking comes from, seasons.

- **Four numbers** at the top: items that need restocking (and how many are
  already out of stock), moves between branches instead of buying, stock that
  may expire before it sells, and stock that does not sell (with its value).
  Under each number one line says what it counts. Click a number to open its
  detail screen.
- **Today's tasks**: one list, most urgent first. Restocking first (red when it
  runs out within the delivery time), then moves to the branch where an item
  sells faster, then stock that may expire, then stock that does not sell.
  Each line is written as sentences: what is happening ("Runs out in 3 days",
  "Not one sold in the last 8 weeks"), why (how much it sells a day or a week,
  how many are left, how long a delivery takes, what is already on order),
  and our suggestion (buy 48 from a supplier, transfer from a branch, wait for
  the main warehouse, put it on offer, return it to the supplier, sell it
  together with an item bought with it). Stock that does not sell also shows
  the money tied up in it. Warehouses are named the way people say them
  ("Stores", not "Stores - LUMD"). **Prepare the request** on a line makes the
  ERPNext Material Request for that item alone, **Request all shortages** for
  every shortage shown. The same preview and the same checks as on the detail
  screens (section 2a). The buttons show only to people who may make requests.
- **Product ideas**: items that sell in another branch and are missing here,
  items often bought together, and trending products (when switched on).
  Each box says in one line what it is and what to do with it.

Every part follows its own switch in the settings, and the same permissions
as its detail screen: a person limited to some branches sees those branches.
The numbers are the detail screens' numbers, worked out once.

### The detail screens

The app shows them, and all eight are also ERPNext reports in the desk, so
they sort, filter, export to Excel and print like any other report, in
English or Arabic, light or dark.

In the app each screen starts with one sentence on what it is for, and shows
its most useful columns first (for Stock health: item, branch, status,
suggestion, on shelf, sold, money tied up). **Show all columns** shows the
rest, **Save for Excel** always saves every column. **What the columns mean**
explains each column on screen in plain words (for example ABC, demand
pattern, lift). **How we calculated this** shows what the numbers are based on.

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
| Shelf capacity | How much the warehouse can hold of the item (ERPNext Putaway Rule). Blank when there is no rule |
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
- **Warehouse does not sell**: the warehouse sold nothing at all in the
  window (Stores, Work In Progress, Finished Goods, a store room). Its stock
  is not counted as not selling and gets no discount. The main warehouse is
  never put here, it supplies the outlets.
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

### Bundle ideas (Shelf Bundle Ideas)

Pairs of items your customers buy together that make a natural set, ready to
sell as one bundle at a small discount. In the app they are cards under
**Product ideas > Bundle ideas**, one per idea: the bundle's name, the two
items, why they belong together, how many invoices had both, the **Price of
the two**, the **Bundle price**, what the **Customer saves** and **Your
profit** on the cost.

How the ideas are found. Once a week Lumen Shelf takes the pairs that were on
3 or more invoices together and at least 1.5 times as often as chance, both
enabled stock items for sale, both in stock, not already in a Product Bundle,
up to 30 pairs. Pairs with an item that does not sell (No sales, Slow,
Overstock) come first, since a set helps it sell. It sends Lumen's AI service
the company's country and, per pair, the two item names and item groups,
never a quantity, a price, a customer or the shop's name. The AI says which
pairs are a natural set (tea with sugar, not jeans with a phone) and gives
each a short name in English and Arabic. The others are kept as **Not a
match**, under the cards. An answer is kept 30 days on the service, so a pair
already asked about costs nothing.

The price is worked out by Lumen Shelf, never by the AI: the two selling
prices in the selling price list (Selling Settings) less the **Bundle
discount** (10% unless changed). The cost of each is its last purchase rate,
else its valuation rate. When the profit on that price would fall under the
**Minimum profit on a bundle** (15% unless changed), the price is raised to
keep it and the discount is smaller, and the card says so. When even the full
price leaves less than that, the bundle is sold at the full price. An item
without a selling price is shown with a note and cannot be made a bundle yet.

**Create bundle** (Shelf Manager or System Manager, who may also create Items,
Product Bundles and Item Prices in ERPNext) makes three things the ERPNext
way, all or none: an item named after the bundle (in the language of the
person who presses it) that is not kept in stock, a Product Bundle of the two
items (one of each) and its selling price in the price list. Selling the
bundle in ERPNext takes the two items out of stock. **Not interested** drops
the idea for good. **Ask for new ideas** asks again now.

At the till. LumenPOS sells the bundle item on ERPNext 14, 15 and 16. The
price goes in the selling price list of Selling Settings: if an outlet's POS
Profile uses another price list, add the bundle's price there too. A barcode
on the bundle item is not needed, but it makes scanning work. On ERPNext 13
no bundle is made: ERPNext 13's own point of sale stops working while a
Product Bundle exists. The ideas are still shown, to sell the two together
with a Pricing Rule.

Set up: the same URL, API Key and API Secret as trending products, in
**Lumen Shelf Settings > Lumen's AI service**. Switch on **Suggest bundles**.
It uses the same free allowance and credit as trending products.

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

### Trending products (Shelf Trending Products)

Products rising in Google searches, in the company's country and worldwide,
that the shop does not sell yet. Per suggestion: the **Item Group** it fits,
the **Product**, **Why** (one sentence), **Where** (in your country or
worldwide), the **Google search** behind it and its **Search growth (%)**
over the last 90 days, and the day it was **Found on**. A Shelf Manager can
open a product and set its status to **Dismissed**: it is not suggested again.

How it works. Once a week Lumen Shelf asks Lumen's trends service. It sends
the company's country, its best selling item groups (up to 12) and the names
of the items in them (up to 40 each). Never a quantity, a price, a customer or
the shop's name. The service reads the related Google searches through
DataForSEO and asks an AI (Claude) which rising products the shop does not
carry, in English and Arabic. A product the shop already has as an item, by
name in either language, is left out.

Set up: Lumen gives the shop a URL, an API Key and an API Secret. Type them in
**Lumen Shelf Settings > Lumen's AI service**, switch on **Suggest trending
products**, and press **Refresh trending products now** (or wait for the
week). The answer takes a few minutes. **Result of the last refresh** says what
happened.

Credit. Each shop has a free allowance on the trends service every month (set
by Lumen, renewed on the 1st). Beyond it, the service uses the shop's prepaid
credit. The settings show the **Credit balance** and the **Free allowance left
this month** (in US dollars, at the service's own cost), refreshed after each
run or with **Check credit**. **Top up credit** opens Lumen's contact: Lumen
adds the credit once paid. When the allowance and the credit are both used up,
the shop gets no new suggestions until it tops up or the month turns, and the
rest of Lumen Shelf works as before. The screen says when the credit runs low.

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
  (their items, groups and the groups under them, brands, tags, exclusions,
  POS profiles' warehouses and weekdays). A promotion limited to some hours
  of the day counts as a promotion day. A rule with no end date is a standing price: it is already in
  the sales history.

**Shelf capacity.** When an item has an ERPNext **Putaway Rule** for a
warehouse (Stock > Putaway Rule: how much of it the warehouse can hold), the
suggestion never fills that warehouse above it: the order-up-to level is at
most the capacity. A warehouse already filled to its capacity is not running
low, even below its reorder point. When rounding a purchase up to whole packs
would overflow the capacity, it buys one pack less (unless that leaves none,
or less than the minimum order). Stock above the capacity counts as surplus
that another outlet can take. A disabled rule, or no rule, changes nothing.

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
- **Respect shelf capacity** (on): uses ERPNext's Putaway Rules, see section 3.
- **Suggest trending products** and **Suggest bundles** (off until Lumen
  gives a key), with **Bundle discount (%)** (10) and **Minimum profit on a
  bundle (%)** (15). Both use **Lumen's AI service**: its URL, API Key and API
  Secret, and the credit, see section 2.
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
- **Trending products**: every role that sees the lists. Refresh now and
  Dismissed: Shelf Manager and System Manager.
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

### 0.13.0 (2026-11-05)
Bundle ideas, and Lumen Shelf becomes open source.
- Licence: GNU General Public License v3 (license.txt), listed on the Frappe
  Cloud Marketplace. Lumen's AI service stays a separate service run by
  Lumen. See the Privacy Policy and Terms of Service in docs/.
- New: Product ideas > Bundle ideas. Pairs bought together that make a
  natural set, checked by Lumen's AI service (names only), each with a name,
  a price (10% off the two, at least 15% profit kept, both in the settings)
  and Create bundle, which makes the ERPNext item, Product Bundle and price.
- Today shows the best bundle ideas among the product ideas.
- ERPNext 13: the ideas are shown but no bundle is made, since ERPNext 13's
  point of sale stops working while a Product Bundle exists.
- Settings: the service's URL, keys and credit are in their own section,
  Lumen's AI service, used by trending products and bundle ideas.

### 0.12.0 (2026-11-04)
The app explains itself.
- Today: every task is written as sentences, what is happening, why and our
  suggestion, with the money tied up in stock that does not sell. Each number
  says what it counts, each idea box what to do with it. A three step welcome
  note (Got it, How it works). The technical line moved behind How we
  calculated this.
- Warehouses without the company's short name ("Stores", not "Stores - LUMD").
- Detail screens: a sentence on what each is for, the main columns first
  (Show all columns for the rest, the Excel file keeps them all), What the
  columns mean, and the item name opens the item.
- Arabic: in "Worth 25,206.46 USD" the amount no longer flips.

### 0.11.0 (2026-11-03)

- Lumen Shelf is now one app of its own at /shelf, like LumenPOS: Today, every
  detail screen, product ideas and the settings, with its own menu, in
  English and Arabic, light and dark, on a computer or a phone. The apps
  screen and the side menu open it. The numbers and permissions are the
  reports' own.

### 0.10.1 (2026-11-03)

- A warehouse that sold nothing at all in the window (Work In Progress,
  Finished Goods, a store room) is no longer listed as stock that does not
  sell. Its new status is **Warehouse does not sell**.
- The page's branch filter was too narrow and cut off its text.

### 0.10.0 (2026-11-02)

- One page for today: the four numbers that matter, one list of tasks with a
  **Request** button on each line, and product ideas. Lumen Shelf now opens on
  it. The eight screens stay as detail screens behind it.

### 0.9.0 (2026-11-01)

- Trending products: products rising in Google searches in your country and
  worldwide that you do not sell yet, with the reason in English and Arabic.
  New screen **Trending products**, refreshed once a week by Lumen's trends
  service. Only names are sent, never quantities, prices or customers.
- Switch **Suggest trending products** (off by default, needs a key from Lumen).
- Credit: a free allowance each month, then prepaid credit that Lumen tops up.
  **Check credit** and **Top up credit** in the settings, a warning when low.

### 0.8.0 (2026-10-31)

- Shelf capacity from ERPNext's own Putaway Rules: a suggestion never fills a
  warehouse above it, a full warehouse is not running low, and packs round
  down when a whole pack would overflow it.
- Running low shows the capacity. Switch **Respect shelf capacity**.

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
- Named Lumen Shelf (called Lumen Restock while it was built).
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
