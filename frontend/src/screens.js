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

// What each column means, in plain words. Shown under "What the columns mean"
// for the columns on screen.
function columnHelp() {
	return {
		item_name: __("The item."),
		warehouse: __("The branch or warehouse."),
		on_shelf: __("How many you have now, less what the till has sold and not yet booked."),
		daily_sales: __("How many it sold on an average day while it was in stock."),
		forecast: __("How many we expect it to sell a day from now on."),
		days_left: __("How many days what you have now will last at the expected sales."),
		on_order: __("Already ordered or requested and not received yet."),
		reorder_point: __("When stock falls to this number, it is time to order again."),
		suggested_qty: __("How many to bring in so it lasts until the next delivery and the days of cover you chose."),
		source: __("Where it should come from: another branch or warehouse, or a supplier."),
		supplier: __("The supplier we suggest, from the item's settings or the last purchase."),
		season_factor: __("How last year's sales in the coming weeks change the forecast. 1.5 means 50% more."),
		promo_factor: __("How a planned promotion raises the forecast."),
		lead_time: __("How many days a delivery usually takes."),
		from_warehouse: __("The branch or warehouse that sends."),
		to_warehouse: __("The branch or warehouse that receives."),
		qty: __("How many to move."),
		reason: __("Why: it is running low there, or it sells faster there."),
		to_days_left: __("How many days the receiving branch has left."),
		status: __("No sales: nothing sold. Slow: sells too little for what you hold. Overstock: far more than it needs. OK: fine."),
		action: __("What we suggest doing with stock that does not sell."),
		sold_qty: __("How many it sold in the weeks we looked at."),
		excess_value: __("The value of the stock above what it needs: money tied up."),
		excess_qty: __("How many you hold above what it needs."),
		abc: __("A: the items that bring most of your sales. B: the middle. C: the items that bring little."),
		pattern: __("How it sells: steady, uneven, now and then, or rarely and in big amounts."),
		trend_status: __("Rising or falling: whether it sells more or less lately than before."),
		trend: __("How much more or less it sells lately, in percent."),
		lost_value: __("Sales missed on the days it was out of stock."),
		expiry_risk_value: __("The value of what may pass its expiry date before it sells."),
		next_promotion: __("The next promotion planned for it."),
		next_from: __("When the promotion starts."),
		lift: __("How many times more it sells. 2 means twice as many."),
		extra_qty: __("The extra quantity added to the suggestion for the promotion."),
		product: __("A product people search for more and more."),
		item_group: __("The group of items it belongs to."),
		growth: __("How much the searches for it grew, in percent."),
		sells_in: __("The branches where it sells."),
		start_qty: __("A first quantity to try in this branch."),
		partner_name: __("The item bought with it."),
		together: __("On how many invoices the two were bought together."),
		forecast_qty: __("What we expected it to sell in the last 14 days."),
		actual_qty: __("What it really sold."),
		error_pct: __("How far the forecast was from what sold. Closer to 0 is better."),
	};
}

export function screens(boot) {
	const all = [
		{
			name: "running_low",
			title: __("Running low"),
			short: __("Low items"),
			icon: "low",
			scope: "running_low",
			intro: __("Items that will run out before a new delivery can arrive, and how many to bring in. Create material requests prepares them in ERPNext for the lines shown."),
			main: ["item_name", "warehouse", "on_shelf", "days_left", "suggested_qty", "source", "supplier"],
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
			intro: __("Stock to move from one branch to another instead of buying more: where it runs low, or where it sells faster."),
			main: ["item_name", "from_warehouse", "to_warehouse", "qty", "reason", "to_days_left"],
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
			intro: __("How each item sells in each branch, and what to do with stock that does not sell."),
			main: ["item_name", "warehouse", "status", "action", "on_shelf", "sold_qty", "excess_value"],
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
		{
			name: "promotions",
			title: __("Promotions"),
			icon: "tag",
			intro: __("How much more each item sold on offer, and the extra stock planned for the next promotion."),
			main: ["item_name", "warehouse", "next_promotion", "next_from", "lift", "extra_qty"],
			filters: [company, warehouse()],
		},
		{
			name: "trending_products",
			title: __("Trending in the market"),
			icon: "spark",
			idea: 1,
			intro: __("Products people search for more and more in your country, that you do not sell yet."),
			main: ["product", "reason", "item_group", "growth"],
			ownHelp: { reason: __("Why it may suit your shop.") },
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
		{
			name: "assortment_gaps",
			title: __("Missing in a branch"),
			icon: "gap",
			idea: 1,
			intro: __("Items that sell well in one branch and that another branch does not stock at all. Worth trying there."),
			main: ["item_name", "warehouse", "sells_in", "daily_sales", "start_qty"],
			filters: [company, warehouse()],
		},
		{
			name: "bought_together",
			title: __("Often bought together"),
			icon: "link",
			idea: 1,
			intro: __("Customers buy these on the same invoice. Put them side by side, or sell them as a set."),
			main: ["item_name", "partner_name", "together"],
			filters: [company, { fieldname: "item_code", type: "link", doctype: "Item", label: __("With item") }],
		},
		{
			name: "forecast_accuracy",
			title: __("Forecast accuracy"),
			icon: "target",
			intro: __("How close our forecast of 14 days ago came to what really sold. It shows whether you can trust the suggestions."),
			main: ["item_name", "warehouse", "forecast_qty", "actual_qty", "error_pct"],
			filters: [company, warehouse()],
		},
	];
	const help = columnHelp();
	return all.filter((s) => boot.screens && boot.screens[s.name]).map((s) => ({ ...s, help: { ...help, ...(s.ownHelp || {}) } }));
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
