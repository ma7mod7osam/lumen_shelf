// The detail screens. Each one shows a report's own rows (restock/app.py
// screen), with that report's filters and colours. Colours: red, amber,
// blue and grey only (never green, Lumen rule).
import { __ } from "./store.js";

const company = { fieldname: "company", type: "company" };
const warehouse = () => ({ fieldname: "warehouse", type: "link", doctype: "Warehouse", label: __("Branch or warehouse") });
const itemGroup = () => ({ fieldname: "item_group", type: "link", doctype: "Item Group", label: __("Item group") });

function opts(list) {
	return [{ value: "", label: __("All") }].concat(list.map(([value, label]) => ({ value, label })));
}

// cell look: a tone (danger, warning, blue, muted), bold, or a text of its own
export function look(name, col, row) {
	const f = col.fieldname;
	const v = row[f];
	const has = v !== null && v !== undefined && v !== "" && v !== 0;
	switch (name) {
		case "running_low":
			if (f === "days_left" && v !== null && v !== undefined) return { tone: v <= (row.lead_time || 0) ? "danger" : "warning", bold: 1 };
			if (f === "season_factor" && has) return { tone: v > 1 ? "blue" : "warning", bold: 1 };
			if (f === "suggested_qty" && has) return { bold: 1 };
			break;
		case "transfers":
			if (f === "qty") return { bold: 1 };
			if (f === "reason") return { tone: row.reason_key === "running_low" ? "danger" : "blue" };
			break;
		case "stock_health":
			if (f === "status")
				return { tone: { "No sales": "danger", Slow: "warning", Overstock: "warning" }[row.status_key] || "muted", bold: 1 };
			if (f === "trend_status" && row.trend_key) return { tone: row.trend_key === "Rising" ? "blue" : "warning", bold: 1 };
			if (f === "trend" && v !== null && v !== undefined) return { text: (v > 0 ? "+" : "") + Number(v).toFixed(1) + "%" };
			if (f === "action" && row.action_key) return { bold: 1 };
			if ((f === "expiry_risk_value" || f === "lost_value") && has) return { tone: "danger" };
			if (f === "days_left" && v > 365) return { text: "365+" };
			if (f === "abc" && v === "A") return { bold: 1 };
			break;
		case "promotions":
			if (f === "lift" && has) return { tone: v > 1 ? "blue" : null, bold: 1 };
			if (f === "promo_factor" && has) return { tone: "blue", bold: 1 };
			if (f === "extra_qty" && has) return { bold: 1 };
			break;
		case "bought_together":
			if (f === "lift" && v >= 2) return { tone: "blue", bold: 1 };
			break;
		case "assortment_gaps":
			if (f === "start_qty" && has) return { bold: 1 };
			break;
		case "trending_products":
			if (f === "growth" && v >= 100) return { tone: "blue", bold: 1 };
			if (f === "product") return { bold: 1 };
			break;
		case "forecast_accuracy":
			if ((f === "error_pct" || f === "difference") && v !== null && v !== undefined) {
				const text = (v > 0 ? "+" : "") + Number(v).toFixed(1) + (f === "error_pct" ? "%" : "");
				return { text, tone: f === "error_pct" && Math.abs(v) >= 50 ? "danger" : null };
			}
			break;
	}
	return null;
}

export function screens(boot) {
	const all = [
		{
			name: "running_low",
			title: __("Running low"),
			short: __("Low items"),
			icon: "low",
			scope: "running_low",
			filters: [
				company,
				warehouse(),
				itemGroup(),
				{
					fieldname: "source",
					type: "select",
					label: __("Restock by"),
					options: opts([
						["Transfer", __("By transfer")],
						["Buy", __("By purchase")],
					]),
				},
			].concat(boot.budget_plan ? [{ fieldname: "budget", type: "number", label: __("Budget") }] : []),
		},
		{
			name: "transfers",
			title: __("Transfer suggestions"),
			short: __("Branch moves"),
			icon: "move",
			scope: "transfers",
			filters: [
				company,
				{ fieldname: "from_warehouse", type: "link", doctype: "Warehouse", label: __("From branch") },
				{ fieldname: "to_warehouse", type: "link", doctype: "Warehouse", label: __("To branch") },
				{
					fieldname: "reason",
					type: "select",
					label: __("Reason"),
					options: opts([
						["Running low there", __("Running low there")],
						["Sells faster there", __("Sells faster there")],
					]),
				},
			],
		},
		{
			name: "stock_health",
			title: __("Stock health"),
			icon: "health",
			filters: [
				company,
				warehouse(),
				{
					fieldname: "status",
					type: "select",
					label: __("Status"),
					options: opts([
						["No sales", __("No sales")],
						["Slow", __("Slow")],
						["Overstock", __("Overstock")],
						["Too new", __("Too new")],
						["Warehouse does not sell", __("Warehouse does not sell")],
						["OK", __("OK")],
					]),
				},
				{ fieldname: "abc", type: "select", label: __("ABC"), options: opts([["A", "A"], ["B", "B"], ["C", "C"]]) },
				{
					fieldname: "trend",
					type: "select",
					label: __("Trend"),
					options: opts([
						["Rising", __("Rising")],
						["Falling", __("Falling")],
					]),
				},
			],
		},
		{ name: "promotions", title: __("Promotions"), icon: "tag", filters: [company, warehouse()] },
		{
			name: "trending_products",
			title: __("Trending in the market"),
			icon: "spark",
			idea: 1,
			filters: [
				company,
				itemGroup(),
				{
					fieldname: "region",
					type: "select",
					label: __("Where"),
					options: opts([
						["In the country", __("In the country")],
						["Worldwide", __("Worldwide")],
					]),
				},
			],
		},
		{ name: "assortment_gaps", title: __("Missing in a branch"), icon: "gap", idea: 1, filters: [company, warehouse()] },
		{
			name: "bought_together",
			title: __("Often bought together"),
			icon: "link",
			idea: 1,
			filters: [company, { fieldname: "item_code", type: "link", doctype: "Item", label: __("With item") }],
		},
		{ name: "forecast_accuracy", title: __("Forecast accuracy"), icon: "target", filters: [company, warehouse()] },
	];
	return all.filter((s) => boot.screens && boot.screens[s.name]);
}

// the desk report a Today card or idea points at, as a screen of the app
export const REPORT_SCREEN = {
	"Shelf Running Low": "running_low",
	"Shelf Transfers": "transfers",
	"Shelf Stock Health": "stock_health",
	"Shelf Promotions": "promotions",
	"Shelf Trending Products": "trending_products",
	"Shelf Assortment Gaps": "assortment_gaps",
	"Shelf Bought Together": "bought_together",
	"Shelf Forecast Accuracy": "forecast_accuracy",
};
