"""Every user-facing string has Arabic, our file never renames text Frappe or
ERPNext already translate (Frappe merges every app's translations into one
table), and no string carries the characters the owner banned."""

import csv
import os
import re
import unittest

import frappe

from lumen_restock import i18n_strings

DIACRITICS = re.compile("[ً-ْٰ]")
DASHES = ("—", "–")


def ours():
	path = frappe.get_app_path("lumen_restock", "translations", "ar.csv")
	with open(path, encoding="utf-8") as fh:
		return {row[0]: row[1] for row in csv.reader(fh) if len(row) >= 2}


def theirs():
	"""Arabic from every other installed app, CSV and .po."""
	full = {}
	for app in frappe.get_installed_apps():
		if app == "lumen_restock":
			continue
		path = frappe.get_app_path(app, "translations", "ar.csv")
		if os.path.exists(path):
			with open(path, encoding="utf-8") as fh:
				for row in csv.reader(fh):
					if len(row) >= 2 and row[0] and row[1]:
						full[row[0]] = row[1]
		po = frappe.get_app_path(app, "locale", "ar.po")
		if os.path.exists(po):
			from babel.messages.pofile import read_po

			with open(po, "rb") as fh:
				for m in read_po(fh):
					if m.id and m.string and isinstance(m.id, str):
						full[m.id] = m.string
	return full


def site_dict():
	import frappe.translate as t

	frappe.local.lang = "ar"
	for name in ("get_full_dict", "get_all_translations"):
		fn = getattr(t, name, None)
		if fn:
			return fn("ar") or {}
	return {}


class TestTranslations(unittest.TestCase):
	def test_every_string_has_arabic(self):
		mine, other = ours(), theirs()
		missing = [s for s in i18n_strings.collect() if not (mine.get(s) or other.get(s))]
		self.assertEqual(missing, [])

	def test_site_serves_arabic(self):
		d = site_dict()
		self.assertEqual(d.get("Days left"), "الأيام المتبقية")
		self.assertEqual(d.get("Restock Running Low"), "أصناف توشك على النفاد")

	def test_no_row_renames_frappe_or_erpnext(self):
		other = theirs()
		clash = sorted(s for s in ours() if s in other)
		self.assertEqual(clash, [])

	def test_no_unused_rows(self):
		used = set(i18n_strings.collect())
		self.assertEqual(sorted(s for s in ours() if s not in used), [])

	def test_banned_characters(self):
		texts = list(i18n_strings.collect()) + list(ours().values())
		for t in texts:
			self.assertFalse(any(d in t for d in DASHES), t)
			self.assertNotIn(";", t)
			self.assertIsNone(DIACRITICS.search(t), t)
