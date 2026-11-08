"""Trending products (0.9.0): products rising in Google searches, in the
shop's country and worldwide, that the shop does not sell yet.

The work is done by Lumen's trends service (the hub, app lumen_trends, on a
Lumen server), which holds Lumen's keys for the search data and the AI. This
side sends it names only: the company's country, its best selling item groups
and the names of the items in them. Never a quantity, a price, a customer or
the shop's name. The shop's own key for the hub is in Lumen Shelf Settings.

Once a week (and on the Refresh button) the hub is asked, its answer awaited
in a background job, and the suggestions kept in Shelf Trend Suggestion. A
suggestion the shop dismissed is not shown again. Off by default: it needs
a key from Lumen.
"""

import time

import frappe
import requests
from frappe import _
from frappe.utils import add_days, flt, getdate, now_datetime, nowdate

from lumen_shelf.restock import access, compat
from lumen_shelf.restock.settings import DOCTYPE, get_settings

CONTRACT = 1
MAX_GROUPS = 12
MAX_ITEMS = 40
SUGGESTION = "Shelf Trend Suggestion"
STATUS_NEW = "New"
STATUS_DISMISSED = "Dismissed"
REGION_LOCAL = "In the country"
REGION_GLOBAL = "Worldwide"
REGIONS = {"local": REGION_LOCAL, "global": REGION_GLOBAL}
POLL_EVERY = 15  # seconds
POLL_FOR = 25 * 60
TIMEOUT = 60
LOW_CREDIT = 1.0  # USD: below this the shop is told to top up


class HubError(Exception):
	pass


# ---- set up

def hub_config():
	doc = frappe.get_single(DOCTYPE)
	url = (doc.get("trends_url") or "").strip().rstrip("/")
	key = (doc.get("trends_api_key") or "").strip()
	secret = doc.get_password("trends_api_secret", raise_exception=False) if doc.get("trends_api_secret") else ""
	return url, key, secret or ""


def configured():
	return all(hub_config())


# ---- what is sent

def window(s, today=None):
	end = add_days(getdate(today or nowdate()), -1)
	return add_days(end, -(s["history_weeks"] * 7 - 1)), end


def group_sales(company, start, end):
	"""{item group: sales value in the window}, net of returns: POS Invoices,
	and Sales Invoices that are not a POS consolidation (counted once)."""
	rows = frappe.db.sql(
		"""select it.item_group, sum(x.amount) from (
			select i.item_code, i.base_net_amount amount
			from `tabPOS Invoice Item` i join `tabPOS Invoice` p on p.name = i.parent
			where p.docstatus=1 and p.company=%(company)s and p.posting_date between %(start)s and %(end)s
			union all
			select i.item_code, i.base_net_amount
			from `tabSales Invoice Item` i join `tabSales Invoice` s on s.name = i.parent
			where s.docstatus=1 and s.is_consolidated=0 and s.company=%(company)s
				and s.posting_date between %(start)s and %(end)s
		) x join `tabItem` it on it.name = x.item_code
		where ifnull(it.item_group, '') != ''
		group by it.item_group""",
		{"company": company, "start": start, "end": end},
	)
	return {g: flt(v) for g, v in rows}


def selling_groups(company, start, end, limit=MAX_GROUPS):
	"""The item groups that brought the most sales in the window. Only their
	names leave the site, in name order (the ranking stays here)."""
	sales = group_sales(company, start, end)
	ranked = sorted(sales, key=lambda g: (-round(sales[g], 6), g))[:limit]
	return sorted(ranked)


def group_items(company, group, start, end):
	"""Up to MAX_ITEMS names of the group's sales items: those sold in the
	window first, then the rest, each part in name order (no ranking leaves)."""
	sold = {
		r[0]
		for r in frappe.db.sql(
			"""select distinct i.item_code from `tabSales Invoice Item` i join `tabSales Invoice` s on s.name = i.parent
			where s.docstatus=1 and s.company=%(company)s and s.posting_date between %(start)s and %(end)s and i.item_group=%(group)s
			union select distinct i.item_code from `tabPOS Invoice Item` i join `tabPOS Invoice` p on p.name = i.parent
			where p.docstatus=1 and p.company=%(company)s and p.posting_date between %(start)s and %(end)s and i.item_group=%(group)s""",
			{"company": company, "start": start, "end": end, "group": group},
		)
	}
	items = frappe.get_all(
		"Item",
		filters={"item_group": group, "disabled": 0, "is_sales_item": 1},
		fields=["name", "item_name"],
		order_by="item_name asc",
	)
	ordered = [i for i in items if i.name in sold] + [i for i in items if i.name not in sold]
	out = []
	for i in ordered:
		n = (i.item_name or i.name).strip()
		if n and n not in out:
			out.append(n)
		if len(out) >= MAX_ITEMS:
			break
	return out


def payload(company, s=None, today=None):
	s = s or get_settings()
	country = frappe.db.get_value("Company", company, "country")
	if not country:
		raise HubError(_("Set the country on company {0}: the trends are read for that country.").format(company))
	start, end = window(s, today)
	groups = [{"name": g, "items": group_items(company, g, start, end)} for g in selling_groups(company, start, end)]
	if not groups:
		raise HubError(_("{0} has no sales in the last {1} weeks to learn its item groups from.").format(company, s["history_weeks"]))
	return {"contract": CONTRACT, "country": country, "groups": groups}


# ---- the hub

def call_hub(method, data=None, params=None):
	url, key, secret = hub_config()
	if not (url and key and secret):
		raise HubError(_("Fill in the trends service URL, API Key and API Secret in Lumen Shelf Settings."))
	headers = {"Authorization": "token %s:%s" % (key, secret), "Accept": "application/json"}
	try:
		if data is not None:
			r = requests.post(url + "/api/method/" + method, json=data, headers=headers, timeout=TIMEOUT)
		else:
			r = requests.get(url + "/api/method/" + method, params=params, headers=headers, timeout=TIMEOUT)
	except requests.RequestException:
		raise HubError(_("Could not reach Lumen's trends service."))
	if r.status_code in (401, 403):
		raise HubError(_("Lumen's trends service did not accept the API Key and API Secret."))
	try:
		js = r.json()
	except ValueError:
		raise HubError(_("Lumen's trends service answered {0}.").format(r.status_code))
	if r.status_code != 200:
		raise HubError(_("Lumen's trends service answered: {0}").format(_hub_message(js) or r.status_code))
	return js.get("message") or {}


def _hub_message(js):
	"""The hub's own words from a Frappe error reply."""
	import json

	try:
		for m in json.loads(js.get("_server_messages") or "[]"):
			return frappe.utils.strip_html(json.loads(m).get("message") or "")[:300]
	except Exception:
		pass
	return (js.get("exception") or "").split(":", 1)[-1].strip()[:300]


def refused(code):
	"""The hub says why in a code, the shop says it in its own language."""
	if code == "budget":
		return _("Lumen's trends service has used its budget for this month. It will be asked again next week.")
	if code == "shop_limit":
		return _("This shop has used its free allowance and credit on Lumen's trends service. Top up credit to go on.")
	return _("Lumen's trends service could not finish this time. It will be asked again next week.")


def keep_credit(c):
	"""What the hub says the shop may still spend, shown in the settings."""
	if not isinstance(c, dict):
		return
	frappe.db.set_value(
		DOCTYPE,
		DOCTYPE,
		{
			"trends_credit": flt(c.get("balance")),
			"trends_free_left": flt(c.get("free_left")),
			"trends_available": flt(c.get("available")),
			"trends_topup_url": (c.get("topup_url") or "")[:500],
		},
		update_modified=False,
	)


def credit_note():
	"""A line to add when the credit runs low, else ''."""
	if not configured():
		return ""
	if flt(frappe.db.get_single_value(DOCTYPE, "trends_available")) < LOW_CREDIT:
		return _("Credit on Lumen's trends service is running low. Top up from Lumen Shelf Settings to keep getting suggestions.")
	return ""


def ask(company, s=None, wait=True):
	"""The hub's suggestions for the company: a list of dicts."""
	return exchange(payload(company, s), wait=wait).get("suggestions") or []


def exchange(request, wait=True):
	"""Send a request to the hub, wait for its answer and return it (Done).
	Used by trending products and by bundle ideas (restock/bundles.py)."""
	sub = call_hub("lumen_trends.api.suggest", data={"request": request})
	keep_credit(sub.get("credit"))
	if sub.get("status") == "Failed":
		raise HubError(refused(sub.get("code")))
	ticket = sub.get("ticket")
	if not ticket:
		raise HubError(_("Lumen's trends service gave no ticket."))
	deadline = time.monotonic() + POLL_FOR
	while True:
		res = call_hub("lumen_trends.api.result", params={"ticket": ticket})
		if res.get("status") in ("Done", "Failed"):
			keep_credit(res.get("credit"))
		if res.get("status") == "Done":
			return res
		if res.get("status") == "Failed":
			raise HubError(refused(res.get("code")))
		if not wait or time.monotonic() > deadline:
			raise HubError(_("Lumen's trends service took too long. It will be asked again next week."))
		time.sleep(POLL_EVERY)


# ---- keeping them

def _norm(t):
	return " ".join((t or "").split()).casefold()


def store(company, suggestions, today=None):
	"""Replace the company's open suggestions. Dropped: a product the shop
	dismissed before, a product it already has as an item (by name, in
	English or Arabic), a group that is not an item group here."""
	have = set()
	for code, name in frappe.db.sql("select name, item_name from `tabItem` where disabled=0"):
		have.add(_norm(code))
		have.add(_norm(name))
	dismissed = set(
		_norm(p)
		for p in frappe.get_all(SUGGESTION, filters={"company": company, "status": STATUS_DISMISSED}, pluck="product")
	)
	frappe.db.delete(SUGGESTION, {"company": company, "status": STATUS_NEW})
	kept, seen = 0, set()
	for r in suggestions or []:
		if not isinstance(r, dict):
			continue
		en, ar = (r.get("product_en") or "").strip(), (r.get("product_ar") or "").strip()
		group = r.get("group")
		key = (group, _norm(en))
		if not en or key in seen or _norm(en) in have or (ar and _norm(ar) in have) or _norm(en) in dismissed:
			continue
		if r.get("region") not in REGIONS or not group or not frappe.db.exists("Item Group", group):
			continue
		seen.add(key)
		frappe.get_doc(
			{
				"doctype": SUGGESTION,
				"company": company,
				"item_group": group,
				"product": en[:140],
				"product_ar": (ar or en)[:140],
				"region": REGIONS[r["region"]],
				"search_term": (r.get("search_term") or "")[:140],
				"growth": max(int(r.get("growth") or 0), 0),
				"reason": (r.get("reason_en") or "")[:500],
				"reason_ar": (r.get("reason_ar") or "")[:500],
				"found_on": getdate(today or nowdate()),
				"status": STATUS_NEW,
			}
		).insert(ignore_permissions=True)
		kept += 1
	return kept


def refresh(company, s=None, wait=True):
	"""One line for the settings page saying what happened."""
	s = s or get_settings()
	if not (s["enabled"] and s["trend_products"]):
		return _("{0}: trending products are switched off.").format(company)
	try:
		kept = store(company, ask(company, s, wait=wait))
	except HubError as e:
		return "%s: %s" % (company, e)
	line = _("{0}: {1} products suggested.").format(company, kept)
	note = credit_note()
	return line + " " + note if note else line


def run(companies):
	lines = []
	for c in companies:
		try:
			lines.append(refresh(c))
		except Exception:
			frappe.log_error(title="Lumen Shelf trending products: %s" % c)
			lines.append(_("{0}: something went wrong, see the Error Log.").format(c))
	frappe.db.set_value(
		DOCTYPE, DOCTYPE, {"last_trends_run": now_datetime(), "last_trends_result": "\n".join(lines)[:1000]}, update_modified=False
	)
	if not frappe.flags.in_test:
		frappe.db.commit()
	return lines


def weekly():
	"""Scheduler, once a week: every company, in a background job."""
	s = get_settings()
	if not (s["enabled"] and s["trend_products"] and configured()):
		return
	companies = frappe.get_all("Company", pluck="name", order_by="name")
	frappe.enqueue("lumen_shelf.restock.trend_products.run", queue="long", timeout=3600, companies=companies)


@frappe.whitelist()
def refresh_now(company=None):
	"""The Refresh button: Shelf Manager or System Manager, the switches on,
	the hub set up. Runs in the background."""
	access.check_view("trend_products")
	if not set(frappe.get_roles()) & set(access.SETTINGS_ROLES) and frappe.session.user != "Administrator":
		frappe.throw(_("Only a Shelf Manager may refresh the trending products."), frappe.PermissionError)
	if company:
		access.check_company(company)
		companies = [company]
	else:
		allowed = compat.allowed_docs("Company")
		companies = [c for c in frappe.get_all("Company", pluck="name", order_by="name") if allowed is None or c in allowed]
	if not configured():
		frappe.throw(_("Fill in the trends service URL, API Key and API Secret in Lumen Shelf Settings."))
	frappe.enqueue("lumen_shelf.restock.trend_products.run", queue="long", timeout=3600, companies=companies)
	return _("Asked Lumen's trends service. The suggestions appear here in a few minutes.")


@frappe.whitelist()
def check_credit():
	"""The Check credit button: asks the hub (free) what the shop may spend."""
	access.check_view("trend_products")
	if not set(frappe.get_roles()) & set(access.SETTINGS_ROLES) and frappe.session.user != "Administrator":
		frappe.throw(_("Only a Shelf Manager may refresh the trending products."), frappe.PermissionError)
	try:
		c = call_hub("lumen_trends.api.balance", params={})
	except HubError as e:
		frappe.throw(str(e))
	keep_credit(c)
	return c


# ---- the screen

def rows(company, item_group=None, region=None, lang=None):
	access.check_view("trend_products")
	access.check_company(company)
	filters = {"company": company, "status": STATUS_NEW}
	if item_group:
		filters["item_group"] = item_group
	if region:
		filters["region"] = region
	arabic = (lang or frappe.local.lang or "en").startswith("ar")
	out = []
	for d in frappe.get_all(
		SUGGESTION,
		filters=filters,
		fields=["name", "item_group", "product", "product_ar", "region", "search_term", "growth", "reason", "reason_ar", "found_on"],
		order_by="item_group asc, growth desc, product asc",
	):
		out.append(
			{
				"name": d.name,
				"item_group": d.item_group,
				"product": (d.product_ar or d.product) if arabic else d.product,
				"reason": (d.reason_ar or d.reason) if arabic else d.reason,
				"region": _(d.region),
				"search_term": d.search_term,
				"growth": d.growth or None,
				"found_on": d.found_on,
			}
		)
	return out
