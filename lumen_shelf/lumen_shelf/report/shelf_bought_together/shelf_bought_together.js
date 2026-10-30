frappe.query_reports["Shelf Bought Together"] = {
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
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "lift" && data.lift >= 2) {
			value = `<span style="color: var(--blue-500, #1463FF); font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
