// Numbers always in Western digits (Lumen rule), in Arabic too.
const cache = {};

function nf(min, max) {
	const k = min + ":" + max;
	if (!cache[k]) cache[k] = new Intl.NumberFormat("en-US", { minimumFractionDigits: min, maximumFractionDigits: max });
	return cache[k];
}

export function num(v, precision = 3) {
	if (v === null || v === undefined || v === "") return "";
	const n = Number(v);
	if (Number.isNaN(n)) return String(v);
	return nf(0, precision).format(n);
}

export function money(v, currency) {
	if (v === null || v === undefined || v === "") return "";
	const n = Number(v);
	if (Number.isNaN(n)) return String(v);
	return nf(2, 2).format(n) + (currency ? " " + currency : "");
}

export function cell(col, row, currency) {
	const v = row[col.fieldname];
	switch (col.fieldtype) {
		case "Int":
			return num(v, 0);
		case "Float":
			return num(v, col.precision === undefined ? 3 : Number(col.precision));
		case "Percent":
			return v === null || v === undefined || v === "" ? "" : num(v, 1) + "%";
		case "Currency":
			return money(v, row.currency || currency);
		default:
			return v === null || v === undefined ? "" : String(v);
	}
}

export const NUMERIC = ["Int", "Float", "Percent", "Currency"];
