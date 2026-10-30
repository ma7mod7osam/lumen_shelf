"""The shop's choices. Every one has a default, so the app works from day one
with nothing filled in (the owner, 2026-10-29: make the setup as easy as
possible). An empty or missing value always means "use the default"."""

import frappe
from frappe.utils import cint

DOCTYPE = "Lumen Shelf Settings"

SOURCE_TRANSFER_FIRST = "Transfer first, then buy"
SOURCE_BUY = "Buy from supplier"
SOURCE_TRANSFER = "Transfer from main warehouse"
SOURCES = (SOURCE_TRANSFER_FIRST, SOURCE_BUY, SOURCE_TRANSFER)

ROLE_MAIN = "Main warehouse"
ROLE_OUTLET = "Outlet"
ROLE_LEAVE_OUT = "Leave out"

# One-sided z for the chance of not running out during the lead time.
SERVICE_LEVELS = {"90%": 1.28, "95%": 1.65, "98%": 2.05, "99%": 2.33}

DEFAULTS = {
	"enabled": 1,
	"cover_days": 14,
	"history_weeks": 8,
	"service_level": "95%",
	"default_lead_time": 7,
	"transfer_lead_time": 2,
	"restock_source": SOURCE_TRANSFER_FIRST,
	"outlet_transfers": 1,
	"min_history_days": 28,
	"stock_health": 1,
	"slow_days": 90,
	"overstock_days": 60,
}

# Allowed ranges, checked when the settings are saved and again when read, so a
# value written around the form can never break the arithmetic.
LIMITS = {
	"cover_days": (1, 365),
	"history_weeks": (2, 26),
	"default_lead_time": (0, 365),
	"transfer_lead_time": (0, 60),
	"min_history_days": (1, 182),
	"slow_days": (7, 3650),
	"overstock_days": (7, 3650),
}

CHECKS = ("enabled", "outlet_transfers", "stock_health")


def _raw():
	if not frappe.db.exists("DocType", DOCTYPE):
		return {}, []
	values = frappe.db.get_singles_dict(DOCTYPE) or {}
	rows = frappe.db.sql(
		"""select company, warehouse, warehouse_role from `tabLumen Shelf Warehouse`
		where parent=%s and parenttype=%s order by idx""",
		(DOCTYPE, DOCTYPE),
		as_dict=True,
	)
	return values, rows


def get_settings():
	"""A plain dict of every setting, defaults filled in."""
	values, rows = _raw()
	out = dict(DEFAULTS)
	for key, default in DEFAULTS.items():
		v = values.get(key)
		if v is None or v == "":
			continue
		if key in CHECKS:
			out[key] = cint(v)
		elif isinstance(default, int):
			n = cint(v)
			lo, hi = LIMITS.get(key, (None, None))
			if n == 0 and key not in ("default_lead_time", "transfer_lead_time"):
				continue  # a cleared number field reads as 0: use the default
			if lo is not None and not (lo <= n <= hi):
				continue
			out[key] = n
		else:
			out[key] = v
	if out["service_level"] not in SERVICE_LEVELS:
		out["service_level"] = DEFAULTS["service_level"]
	if out["restock_source"] not in SOURCES:
		out["restock_source"] = DEFAULTS["restock_source"]
	out["z"] = SERVICE_LEVELS[out["service_level"]]
	out["warehouse_roles"] = [dict(r) for r in rows if r.get("warehouse")]
	out["modified"] = str(values.get("modified") or "")
	return out
