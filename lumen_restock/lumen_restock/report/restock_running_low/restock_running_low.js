frappe.query_reports["Restock Running Low"] = {
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
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "source",
			label: __("Source"),
			fieldtype: "Select",
			options: [
				{ value: "", label: "" },
				{ value: "Transfer", label: __("By transfer") },
				{ value: "Buy", label: __("By purchase") },
			],
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "days_left" && data.days_left !== null && data.days_left !== undefined) {
			const cls = data.days_left <= (data.lead_time || 0) ? "text-danger" : "text-warning";
			value = `<span class="${cls}" style="font-weight: 600">${value}</span>`;
		}
		if (column.fieldname === "suggested_qty" && data.suggested_qty) {
			value = `<span style="font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
