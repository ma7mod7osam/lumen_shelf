"""Every user-facing string in the app: _() in Python, __() in JavaScript, and
labels, descriptions and options in the doctype JSON. Used by the translation
test (tests/test_translations.py) and by dev/i18n_check.py."""

import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = re.compile(r'(?<![A-Za-z_])_\(\s*"((?:[^"\\]|\\.)+)"\s*[,)]')
JS = re.compile(r'__\(\s*"((?:[^"\\]|\\.)+)"\s*[,)]')
SKIP_DIRS = {"tests", "__pycache__", "public", "translations"}
SKIP_FILES = {"i18n_strings.py"}

# Shown through _() with a variable, so no regex finds them.
EXTRA = [
	"Set by Lumen Shelf",  # custom field on Item Reorder (install.py)
	"By transfer",
	"By purchase",
	"Transfer and purchase",
	"Wait for main warehouse",
	"Running low there",
	"Sells faster there",
	"OK",
	"Too new",
	"No sales",
	"Slow",
	"Overstock",
	"Transfer first, then buy",
	"Buy from supplier",
	"Transfer from main warehouse",
	"Shelf Running Low",
	"Shelf Transfers",
	"Shelf Stock Health",
	"Lumen Shelf",
	"Lumen Shelf Settings",
	"Running low",
	"Transfer suggestions",
	"Stock health",
	"Restock",
	"Rising",
	"Falling",
	"Gregorian",
	"Hijri",
	"Shelf Forecast Accuracy",
	"Forecast accuracy",
	"Sales history",
	"Demand pattern",
	"Similar items (brand)",
	"Similar items (group)",
	"Smooth",
	"Erratic",
	"Intermittent",
	"Lumpy",
	"Shelf Bought Together",
	"Shelf Assortment Gaps",
	"Bought together",
	"Assortment gaps",
	"Shelf Promotions",
	"Shelf Trending Products",
	"Shelf Trend Suggestion",
	"Promotions",
	"Sales history, promotions left out",
	"ERPNext pricing rule",
	"LumenPOS promotion",
]


def collect(root=ROOT):
	out = set(EXTRA)
	for base, dirs, files in os.walk(root):
		dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
		for f in files:
			if f in SKIP_FILES:
				continue
			path = os.path.join(base, f)
			if f.endswith(".py"):
				with open(path, encoding="utf-8") as fh:
					out.update(PY.findall(fh.read()))
			elif f.endswith(".js"):
				with open(path, encoding="utf-8") as fh:
					out.update(JS.findall(fh.read()))
			elif f.endswith(".json") and os.sep + "doctype" + os.sep in path:
				with open(path, encoding="utf-8") as fh:
					d = json.load(fh)
				for fl in d.get("fields", []):
					for k in ("label", "description"):
						if fl.get(k):
							out.add(fl[k])
					if fl.get("fieldtype") == "Select" and fl.get("options"):
						out.update(o for o in fl["options"].split("\n") if o and not o.endswith("%"))
	return sorted(s.replace('\\"', '"') for s in out)
