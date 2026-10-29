"""Before the app's tests: a site whose ERPNext setup was never completed gets
it completed, with the same answers ERPNext's own test bootstrap uses.

ERPNext v13 to v15 do this in their own `before_tests` hook. Frappe v16 runs
only the tested app's hooks, and ERPNext v16 has none, so without this a fresh
v16 test site has no customer groups, territories or fiscal year."""

import frappe
from frappe.utils import now_datetime


def setup_done():
	try:
		return bool(frappe.is_setup_complete())
	except Exception:
		return frappe.db.a_row_exists("Company")


def before_tests():
	if setup_done():
		return
	frappe.clear_cache()
	try:
		from erpnext.setup.utils import before_tests as erpnext_before_tests
	except ImportError:
		erpnext_before_tests = None
	if erpnext_before_tests:
		erpnext_before_tests()
		return
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	year = now_datetime().year
	setup_complete(
		{
			"currency": "USD",
			"full_name": "Test User",
			"company_name": "Wind Power LLC",
			"timezone": "America/New_York",
			"company_abbr": "WP",
			"industry": "Manufacturing",
			"country": "United States",
			"fy_start_date": "%d-01-01" % year,
			"fy_end_date": "%d-12-31" % year,
			"language": "english",
			"company_tagline": "Testing",
			"email": "test@erpnext.com",
			"password": "test",
			"chart_of_accounts": "Standard",
		}
	)
	frappe.db.commit()
