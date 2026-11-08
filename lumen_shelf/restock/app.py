"""The Lumen Shelf app at /shelf (owner, 2026-11-03: "one page with
everything, like LumenPOS, so we control it fully").

The screen is our own (frontend/, built into public/shelf), the figures are
not: every screen calls the same report code the desk uses, with the same
checks (our gate in views.load, the Report's roles and ERPNext's report
permission on its ref doctype), so the app and the reports can never
disagree. Nothing here works anything out on its own."""

import json
import os

import frappe
from frappe import _

from lumen_shelf.restock import access, home, settings as st

# screen name in the app -> the report it shows
SCREENS = {
	"running_low": "Shelf Running Low",
	"transfers": "Shelf Transfers",
	"stock_health": "Shelf Stock Health",
	"promotions": "Shelf Promotions",
	"trending_products": "Shelf Trending Products",
	"bundle_ideas": "Shelf Bundle Ideas",
	"assortment_gaps": "Shelf Assortment Gaps",
	"bought_together": "Shelf Bought Together",
	"forecast_accuracy": "Shelf Forecast Accuracy",
}
# the switch each screen follows (access.FEATURES)
SCREEN_FEATURE = {
	"running_low": "running_low",
	"transfers": "transfers",
	"stock_health": "stock_health",
	"promotions": "promotions",
	"trending_products": "trend_products",
	"bundle_ideas": "bundle_ideas",
	"assortment_gaps": "assortment_gaps",
	"bought_together": "bought_together",
	"forecast_accuracy": "forecast_accuracy",
}
# what the app's search boxes may look up, and how
LOOKUPS = {
	"Company": {"fields": ["name"], "search": ["name"]},
	"Warehouse": {"fields": ["name"], "search": ["name"], "filters": {"is_group": 0}},
	"Item Group": {"fields": ["name"], "search": ["name"]},
	"Item": {"fields": ["name", "item_name"], "search": ["name", "item_name"], "filters": {"disabled": 0}},
}
SETTINGS = "Lumen Shelf Settings"
TREND = "Shelf Trend Suggestion"
SKIP_FIELDS = ("Section Break", "Column Break", "Tab Break", "HTML", "Table", "Button")
STRINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_strings.json")


def app_strings():
	"""Every text the app's screen shows, listed by frontend/extract-strings.mjs
	at build time."""
	try:
		with open(STRINGS_FILE, encoding="utf-8") as fh:
			return json.load(fh)
	except (OSError, ValueError):
		return []


def _may_open(user=None):
	"""Viewers, and a settings person even when the app is switched off (or
	nobody could switch it back on from here)."""
	return access.can_view(user) or access.has_settings_role(user)


def _check_open():
	if not _may_open():
		frappe.throw(_("You do not have a role that may see restock suggestions."), frappe.PermissionError)


def _screens(s):
	out = {}
	for name, feature in SCREEN_FEATURE.items():
		switch = access.FEATURES.get(feature)
		on = bool(s["enabled"]) and (not switch or bool(s.get(switch)))
		out[name] = on and _report_allowed(SCREENS[name])
	return out


def _report_allowed(report):
	"""The desk's own two checks for a report: its roles and the report
	permission on its ref doctype (Bin)."""
	doc = frappe.get_cached_doc("Report", report)
	return bool(doc.is_permitted()) and bool(frappe.has_permission(doc.ref_doctype, "report"))


def _theme():
	theme = (frappe.db.get_value("User", frappe.session.user, "desk_theme") or "Light").lower()
	return theme if theme in ("light", "dark", "automatic") else "light"


@frappe.whitelist()
def boot():
	"""Who is looking and what they may open: called once when the app starts."""
	_check_open()
	from lumen_shelf import __version__

	s = st.get_settings()
	lang = frappe.local.lang or "en"
	user = frappe.session.user
	companies = frappe.get_list("Company", fields=["name", "abbr"], order_by="name asc", limit_page_length=0)
	return {
		"version": __version__,
		"user": user,
		"full_name": frappe.utils.get_fullname(user),
		"lang": lang,
		"rtl": lang.split("-")[0] in ("ar", "he", "fa", "ur"),
		"theme": _theme(),
		"enabled": int(bool(s["enabled"])),
		"can_view": int(access.can_view()),
		"can_settings": int(access.has_settings_role()),
		"can_request": int(access.can_request()),
		"screens": _screens(s) if access.can_view() else {},
		"budget_plan": int(bool(s.get("budget_plan"))),
		"company": home.default_company() if access.can_view() else None,
		"companies": [c.name for c in companies],
		# the short name ERPNext adds to each warehouse ("Stores - LUMD"), so
		# the screens can say "Stores"
		"abbrs": {c.name: c.abbr for c in companies},
		"messages": {t: _(t) for t in app_strings()},
	}


@frappe.whitelist()
def overview(company=None, warehouse=None):
	"""The Today screen: home.overview, the same one the desk page used."""
	return home.overview(company=company, warehouse=warehouse)


@frappe.whitelist()
def screen(name, filters=None):
	"""One detail screen: the report's own execute(), so the rows, columns,
	labels and checks are the report's."""
	report = SCREENS.get(name)
	if not report:
		frappe.throw(_("Unknown screen."))
	if isinstance(filters, str):
		filters = json.loads(filters or "{}")
	filters = {k: v for k, v in (filters or {}).items() if v not in (None, "")}
	if not _report_allowed(report):
		frappe.throw(_("You are not permitted to see this screen."), frappe.PermissionError)
	module = "lumen_shelf.lumen_shelf.report.{0}.{0}".format(frappe.scrub(report))
	columns, rows, message, chart, summary = frappe.get_attr(module + ".execute")(filters)
	currency = frappe.get_cached_value("Company", filters.get("company"), "default_currency") if filters.get("company") else None
	return {"columns": columns, "rows": rows, "message": message, "summary": summary or [], "currency": currency}


@frappe.whitelist()
def lookup(doctype, txt="", company=None):
	"""The app's search boxes: ERPNext's own list permissions and User
	Permissions apply (frappe.get_list)."""
	_check_open()
	spec = LOOKUPS.get(doctype)
	if not spec:
		frappe.throw(_("Unknown list."))
	filters = dict(spec.get("filters") or {})
	if doctype == "Warehouse" and company:
		filters["company"] = company
	or_filters = None
	if txt:
		or_filters = [[doctype, f, "like", "%{0}%".format(txt)] for f in spec["search"]]
	return frappe.get_list(
		doctype, filters=filters, or_filters=or_filters, fields=spec["fields"], order_by="name asc", limit_page_length=20
	)


# ---- settings


def _check_settings():
	if not access.has_settings_role():
		frappe.throw(_("Only a Shelf Manager may change the settings."), frappe.PermissionError)


def _field(df):
	out = {
		"fieldname": df.fieldname,
		"fieldtype": df.fieldtype,
		"label": _(df.label) if df.label else "",
		"description": _(df.description) if df.description else "",
		"depends_on": df.depends_on or "",
		"read_only": int(bool(df.read_only)),
	}
	if df.fieldtype == "Select":
		out["options"] = [{"value": o, "label": _(o)} for o in (df.options or "").split("\n") if o]
	if df.fieldtype in ("Link", "Table"):
		out["options"] = df.options
	return out


@frappe.whitelist()
def settings():
	"""The settings screen: the doctype's own fields and values (a password is
	never sent, only whether one is set), and what the app found on its own."""
	_check_settings()
	from lumen_shelf.lumen_shelf.doctype.lumen_shelf_settings.lumen_shelf_settings import detected_setup

	doc = frappe.get_single(SETTINGS)
	meta = frappe.get_meta(SETTINGS)
	fields = [_field(df) for df in meta.fields if df.fieldtype not in ("HTML",)]
	values = {}
	for df in meta.fields:
		if df.fieldtype in SKIP_FIELDS:
			continue
		if df.fieldtype == "Password":
			values[df.fieldname] = ""
			values[df.fieldname + "_set"] = int(bool(doc.get(df.fieldname)))
			continue
		values[df.fieldname] = doc.get(df.fieldname)
	child = frappe.get_meta("Lumen Shelf Warehouse")
	return {
		"fields": fields,
		"values": values,
		"warehouses": [{"company": r.company, "warehouse": r.warehouse, "warehouse_role": r.warehouse_role} for r in doc.warehouses],
		"warehouse_fields": [_field(df) for df in child.fields],
		"detected": detected_setup(),
		"write": int(bool(frappe.has_permission(SETTINGS, "write"))),
	}


@frappe.whitelist(methods=["POST"])
def save_settings(values=None, warehouses=None):
	"""Saved the ERPNext way: doc.save() runs the doctype's own checks and
	permission. A password left empty keeps the one stored."""
	_check_settings()
	values = json.loads(values) if isinstance(values, str) else (values or {})
	warehouses = json.loads(warehouses) if isinstance(warehouses, str) else warehouses
	doc = frappe.get_single(SETTINGS)
	meta = frappe.get_meta(SETTINGS)
	for df in meta.fields:
		if df.fieldtype in SKIP_FIELDS or df.read_only or df.fieldname not in values:
			continue
		v = values[df.fieldname]
		if df.fieldtype == "Password" and not v:
			continue
		doc.set(df.fieldname, v)
	if warehouses is not None:
		doc.set("warehouses", [])
		for r in warehouses:
			if r.get("warehouse"):
				doc.append(
					"warehouses",
					{"company": r.get("company"), "warehouse": r.get("warehouse"), "warehouse_role": r.get("warehouse_role")},
				)
	doc.save()
	return settings()


# ---- trending products


@frappe.whitelist(methods=["POST"])
def dismiss_trend(name):
	"""Not interested: the suggestion is never shown again. ERPNext's write
	permission on the suggestion applies (doc.save)."""
	access.check_view("trend_products")
	doc = frappe.get_doc(TREND, name)
	from lumen_shelf.restock.trend_products import STATUS_DISMISSED

	doc.status = STATUS_DISMISSED
	doc.save()
	return {"name": doc.name, "status": doc.status}
