"""The arithmetic. Pure functions: no database, no Frappe, so every rule here can
be checked on its own and every number traced back to one line.

Words used throughout:
  window       the last `weeks` x 7 whole days, ending yesterday (today is not
               over yet, so it would always read low)
  in stock day a day the item was on the shelf in that warehouse at some point:
               the stock at the start of the day, or after any movement that
               day, was above zero, or something sold that day
  speed        weighted average units sold per in stock day
  sigma        how much the daily sales swing (standard deviation, in stock days)
  lead time    days from asking to having it on the shelf
  reorder point (ROP)   speed x lead time + safety
  order-up-to (target)  ROP + speed x cover days
  position     on shelf + on order - reserved for sales orders
"""

import math

EPS = 1e-9


def window_days(end, weeks):
	"""The dates of the window, oldest first. `end` is the last day (yesterday)."""
	import datetime

	n = int(weeks) * 7
	return [end - datetime.timedelta(days=i) for i in range(n - 1, -1, -1)]


def week_weight(day, end, weeks):
	"""The most recent week weighs `weeks`, the oldest weighs 1."""
	k = (end - day).days // 7
	return weeks - k


def in_stock_days(days, opening_qty, ledger_by_day, sold_by_day):
	"""Which days of `days` count. `ledger_by_day[d]` is (closing qty, highest
	qty after any movement that day) from the Stock Ledger, for days that had a
	movement. A day with no movement keeps the previous day's closing qty."""
	out = set()
	qty = opening_qty or 0.0
	for d in days:
		sold = sold_by_day.get(d, 0.0)
		if d in ledger_by_day:
			close, highest = ledger_by_day[d]
			if qty > EPS or highest > EPS or abs(sold) > EPS:
				out.add(d)
			qty = close
		else:
			if qty > EPS or abs(sold) > EPS:
				out.add(d)
	return out


def speed_and_sigma(days, stocked, sold_by_day, end, weeks):
	"""(speed, sigma, number of in stock days). Days out of stock are left out
	entirely, so an empty shelf never reads as no demand."""
	num = 0.0
	den = 0.0
	values = []
	for d in days:
		if d not in stocked:
			continue
		w = week_weight(d, end, weeks)
		s = sold_by_day.get(d, 0.0)
		num += w * s
		den += w
		values.append(s)
	n = len(values)
	if not n or den <= 0:
		return 0.0, 0.0, 0
	speed = max(num / den, 0.0)
	if n > 1:
		mean = sum(values) / n
		sigma = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
	else:
		sigma = 0.0
	return speed, sigma, n


def safety_stock(z, sigma, lead_days):
	"""Grows with how much sales swing and with the lead time."""
	return z * sigma * math.sqrt(max(lead_days, 0))


def reorder_point(speed, lead_days, safety):
	return speed * lead_days + safety


def order_up_to(rop, speed, cover_days):
	return rop + speed * cover_days


def is_running_low(speed, position, rop):
	return speed > EPS and position <= rop + EPS


def days_left(on_shelf, speed):
	if speed <= EPS:
		return None
	return max(on_shelf, 0.0) / speed


def median(values):
	v = sorted(values)
	n = len(v)
	if not n:
		return None
	mid = n // 2
	return float(v[mid]) if n % 2 else (v[mid - 1] + v[mid]) / 2.0


def round_need(qty, whole):
	"""A shortage is rounded up: half a unit short is one unit short."""
	if qty <= EPS:
		return 0.0
	return float(math.ceil(qty - EPS)) if whole else round(qty, 3)


def round_surplus(qty, whole):
	"""A surplus is rounded down: never move what is not really spare."""
	if qty <= EPS:
		return 0.0
	return float(math.floor(qty + EPS)) if whole else round(qty, 3)


def round_to_pack(qty, pack, min_order):
	"""What to buy, in stock units: at least the minimum order, then up to a
	whole number of packs (the purchase unit's conversion factor)."""
	if qty <= EPS:
		return 0.0
	qty = max(qty, min_order or 0.0)
	if pack and pack > EPS:
		return round(math.ceil(qty / pack - EPS) * pack, 6)
	return float(math.ceil(qty - EPS))


def abc_classes(values):
	"""{key: "A"|"B"|"C"} by share of sales value. The items that make the first
	80% of sales are A, the next 15% B, the rest C. An item is A when the share
	before it is still under 80%, so the top seller is always A."""
	items = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
	total = sum(v for _, v in items if v > 0)
	out = {}
	running = 0.0
	for key, value in items:
		if total <= EPS or value <= EPS:
			out[key] = "C"
			continue
		before = running / total
		out[key] = "A" if before < 0.80 - EPS else ("B" if before < 0.95 - EPS else "C")
		running += value
	return out


# ---- 0.2.0: seasons, trend, lost sales, budget, accuracy

SEASON_MIN_ITEM = 20.0  # units sold in last year's window before an item has its own season
SEASON_MIN_GROUP = 50.0  # the same for its item group
SEASON_CLAMP = (0.25, 4.0)
HORIZON_WEEKS_MAX = 13


def horizon_weeks(days):
	"""The coming weeks a suggestion has to cover (lead time + cover days)."""
	return max(1, min(HORIZON_WEEKS_MAX, int(round(days / 7.0))))


def season_factor(base_qty, base_weeks, horizon_qty, horizon_n):
	"""Last year: the sales rate over the weeks ahead divided by the rate over
	the weeks of the history window. None when last year had no sales in the
	window weeks, so nothing can be learned."""
	if base_qty <= EPS or base_weeks <= 0 or horizon_n <= 0:
		return None
	ratio = (max(horizon_qty, 0.0) / horizon_n) / (base_qty / base_weeks)
	lo, hi = SEASON_CLAMP
	return min(max(ratio, lo), hi)


def pick_calendar(errors, none_error):
	"""The calendar whose backtest error is lowest, only if it beats leaving
	seasons out. `errors` is {name: error or None}."""
	best, best_err = None, none_error
	for name in sorted(errors):
		err = errors[name]
		if err is not None and err < best_err - EPS:
			best, best_err = name, err
	return best


def trend(days, stocked, sold_by_day, min_days=10, min_units=10.0):
	"""Change of the in-stock sales rate, recent half of `days` against the
	earlier half: 0.5 is +50%. None when either half is too thin to judge."""
	half = len(days) // 2
	parts = []
	for chunk in (days[:half], days[half:]):
		n = 0
		qty = 0.0
		for d in chunk:
			if d in stocked:
				n += 1
				qty += sold_by_day.get(d, 0.0)
		parts.append((n, qty))
	(n0, q0), (n1, q1) = parts
	if n0 < min_days or n1 < min_days or q0 + q1 < min_units or q0 <= EPS:
		return None
	return (q1 / n1) / (q0 / n0) - 1.0


def out_of_stock_days(days, stocked):
	"""Days out of stock since the item first was in stock in the window."""
	first = next((i for i, d in enumerate(days) if d in stocked), None)
	if first is None:
		return 0
	return sum(1 for d in days[first:] if d not in stocked)


def accuracy(pairs):
	"""(accuracy, bias) from [(forecast, actual)]: 1 - sum|F-A| / sum A, and
	sum(F-A) / sum A. None when nothing was sold."""
	total = sum(a for _f, a in pairs)
	if total <= EPS:
		return None, None
	err = sum(abs(f - a) for f, a in pairs)
	bias = sum(f - a for f, a in pairs)
	return max(0.0, 1.0 - err / total), bias / total


def fit_budget(lines, budget):
	"""Marks lines, already in priority order, that fit the budget: the running
	total of their cost stays within it. A line that does not fit is skipped and
	a cheaper one after it may still fit. Returns the total spent."""
	spent = 0.0
	for line in lines:
		cost = line.get("cost") or 0.0
		if spent + cost <= budget + EPS:
			spent += cost
			line["in_budget"] = 1
		else:
			line["in_budget"] = 0
		line["running_total"] = spent
	return spent


# ---- 0.3.0: demand patterns, new items, expiry, dead stock, bought together

PATTERN_SMOOTH = "Smooth"
PATTERN_ERRATIC = "Erratic"
PATTERN_INTERMITTENT = "Intermittent"
PATTERN_LUMPY = "Lumpy"
ADI_CUT = 1.32  # Syntetos and Boylan's cut-offs
CV2_CUT = 0.49
SBA_ALPHA = 0.1


def demand_pattern(days, stocked, sold_by_day):
	"""(pattern, adi, cv2) over the in-stock days, or (None, None, None) with
	fewer than 2 days that sold. ADI: in-stock days per day with a sale. CV2:
	the squared coefficient of variation of the sizes of those sales."""
	series = [sold_by_day.get(d, 0.0) for d in days if d in stocked]
	sizes = [q for q in series if q > EPS]
	if len(sizes) < 2:
		return None, None, None
	adi = len(series) / float(len(sizes))
	mean = sum(sizes) / len(sizes)
	var = sum((q - mean) ** 2 for q in sizes) / (len(sizes) - 1)
	cv2 = var / (mean * mean)
	if adi < ADI_CUT:
		pattern = PATTERN_SMOOTH if cv2 < CV2_CUT else PATTERN_ERRATIC
	else:
		pattern = PATTERN_INTERMITTENT if cv2 < CV2_CUT else PATTERN_LUMPY
	return pattern, adi, cv2


def sba(days, stocked, sold_by_day, alpha=SBA_ALPHA):
	"""Syntetos-Boylan corrected Croston: units a day for demand that comes
	now and then. Sizes and intervals between sales are smoothed separately,
	in-stock days only. None with fewer than 2 days that sold."""
	series = [sold_by_day.get(d, 0.0) for d in days if d in stocked]
	z = p = None
	gap = 0
	n = 0
	for q in series:
		gap += 1
		if q > EPS:
			n += 1
			if z is None:
				z, p = q, float(gap)
			else:
				z = z + alpha * (q - z)
				p = p + alpha * (gap - p)
			gap = 0
	if n < 2 or not p:
		return None
	return (1.0 - alpha / 2.0) * z / p


def median_or_none(values, minimum):
	v = [x for x in values if x is not None]
	if len(v) < minimum:
		return None
	return median(v)


def shelf_life_cover(cover_days, shelf_life, lead):
	"""Never plan to hold more than sells before it expires."""
	if not shelf_life or shelf_life <= 0:
		return cover_days
	return max(1.0, min(float(cover_days), shelf_life - lead))


def expiry_risk(batches, speed, today):
	"""Units that will expire before they sell. `batches` is [(expiry date,
	qty)]: the first to expire sells first (FEFO) at `speed` a day."""
	risk = 0.0
	sold_until = 0.0  # units sold up to the expiry of the batch before
	for expiry, qty in sorted(batches, key=lambda b: b[0]):
		if qty <= EPS:
			continue
		days = max((expiry - today).days, 0)
		can_sell = max(speed * days - sold_until, 0.0)
		sells = min(qty, can_sell)
		risk += qty - sells
		sold_until += sells
	return risk


ACTION_MOVE = "Move"
ACTION_RETURN = "Return to supplier"
ACTION_BUNDLE = "Bundle"
ACTION_DISCOUNT = "Discount"


def dead_stock_action(move_to, bought_recently, partner):
	"""What to do with stock that does not sell, in this order."""
	if move_to:
		return ACTION_MOVE
	if bought_recently:
		return ACTION_RETURN
	if partner:
		return ACTION_BUNDLE
	return ACTION_DISCOUNT


def basket_pairs(baskets, min_together=3):
	"""[(a, b, together, confidence a->b, lift)] from baskets (sets of items).
	Both directions. Confidence = baskets with both / baskets with a. Lift =
	confidence / share of baskets with b."""
	total = len(baskets)
	if not total:
		return []
	count = {}
	pair = {}
	for basket in baskets:
		items = sorted(basket)
		for i, a in enumerate(items):
			count[a] = count.get(a, 0) + 1
			for b in items[i + 1 :]:
				pair[(a, b)] = pair.get((a, b), 0) + 1
	out = []
	for (a, b), n in pair.items():
		if n < min_together:
			continue
		for x, y in ((a, b), (b, a)):
			conf = n / float(count[x])
			out.append((x, y, n, conf, conf / (count[y] / float(total))))
	return out
