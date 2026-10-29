frappe.query_reports["Restock Transfers"] = {
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
			fieldname: "from_warehouse",
			label: __("From warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({
				filters: { company: frappe.query_report.get_filter_value("company"), is_group: 0 },
			}),
		},
		{
			fieldname: "to_warehouse",
			label: __("To warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({
				filters: { company: frappe.query_report.get_filter_value("company"), is_group: 0 },
			}),
		},
		{
			fieldname: "reason",
			label: __("Reason"),
			fieldtype: "Select",
			options: [
				{ value: "", label: "" },
				{ value: "Running low there", label: __("Running low there") },
				{ value: "Sells faster there", label: __("Sells faster there") },
			],
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "qty") {
			value = `<span style="font-weight: 600">${value}</span>`;
		}
		if (column.fieldname === "reason") {
			const cls = data.reason_key === "running_low" ? "text-danger" : "text-primary";
			value = `<span class="${cls}">${value}</span>`;
		}
		return value;
	},
};
