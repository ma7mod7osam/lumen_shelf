frappe.query_reports["Shelf Stock Health"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({
				filters: { company: frappe.query_report.get_filter_value("company"), is_group: 0 },
			}),
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: [
				{ value: "", label: "" },
				{ value: "No sales", label: __("No sales") },
				{ value: "Slow", label: __("Slow") },
				{ value: "Overstock", label: __("Overstock") },
				{ value: "Too new", label: __("Too new") },
				{ value: "Warehouse does not sell", label: __("Warehouse does not sell") },
				{ value: "OK", label: __("Healthy") },
			],
		},
		{
			fieldname: "abc",
			label: __("ABC"),
			fieldtype: "Select",
			options: ["", "A", "B", "C"],
		},
		{
			fieldname: "trend",
			label: __("Trend"),
			fieldtype: "Select",
			options: [
				{ value: "", label: "" },
				{ value: "Rising", label: __("Rising") },
				{ value: "Falling", label: __("Falling") },
			],
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "status") {
			const cls = {
				"No sales": "text-danger",
				Slow: "text-warning",
				Overstock: "text-warning",
				OK: "text-muted",
				"Warehouse does not sell": "text-muted",
			}[data.status_key];
			if (cls) value = `<span class="${cls}" style="font-weight: 600">${value}</span>`;
		}
		if (column.fieldname === "trend_status" && data.trend_key) {
			// blue for rising, amber for falling (never green, Lumen rule)
			const style =
				data.trend_key === "Rising" ? "color: var(--blue-500, #1463FF)" : "color: var(--orange-500, #E79913)";
			value = `<span style="${style}; font-weight: 600">${value}</span>`;
		}
		if (column.fieldname === "trend" && data.trend !== null && data.trend !== undefined) {
			// keep the sign on the left in Arabic too: +40% not 40%+
			const sign = data.trend > 0 ? "+" : "";
			value = `<div style="text-align: right"><bdi dir="ltr">${sign}${data.trend.toFixed(1)}%</bdi></div>`;
		}
		if (column.fieldname === "action" && data.action_key) {
			value = `<span style="font-weight: 600">${value}</span>`;
		}
		if (column.fieldname === "expiry_risk_value" && data.expiry_risk_value) {
			value = `<span class="text-danger">${value}</span>`;
		}
		if (column.fieldname === "lost_value" && data.lost_value) {
			value = `<span class="text-danger">${value}</span>`;
		}
		if (column.fieldname === "days_left" && data.days_left > 365) {
			// a year or more of stock: the exact figure is noise
			value = `<div style="text-align: right"><bdi dir="ltr">365+</bdi></div>`;
		}
		if (column.fieldname === "abc" && data.abc === "A") {
			value = `<span style="font-weight: 700">${value}</span>`;
		}
		return value;
	},
};
