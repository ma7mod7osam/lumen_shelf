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
