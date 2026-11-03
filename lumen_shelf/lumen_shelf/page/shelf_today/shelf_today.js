// Lumen Shelf: one page with what needs doing today. The figures come from
// lumen_shelf.restock.home.overview, which uses the same engine and the same
// checks as the detail screens. Colours: red, amber, blue and grey only.
frappe.pages["shelf-today"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Lumen Shelf"), single_column: true });
	const shelf = new LumenShelfToday(page, wrapper);
	wrapper.lumen_shelf = shelf;
	shelf.refresh();
};

frappe.pages["shelf-today"].on_page_show = function (wrapper) {
	if (wrapper.lumen_shelf && wrapper.lumen_shelf.loaded) wrapper.lumen_shelf.refresh();
};

class LumenShelfToday {
	constructor(page, wrapper) {
		this.page = page;
		this.kind = "";
		this.$body = $('<div class="lsh"></div>').appendTo($(wrapper).find(".layout-main-section"));
		this.style();
		this.company = page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			change: () => {
				if (this.data && this.company.get_value() === this.data.company) return;
				// a warehouse of the old company makes no sense: clearing it refreshes
				if (this.warehouse.get_value()) this.warehouse.set_value("");
				else this.refresh();
			},
		});
		this.warehouse = page.add_field({
			fieldname: "warehouse",
			label: __("Branch or warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({ filters: { company: this.company.get_value(), is_group: 0 } }),
			change: () => this.refresh(),
		});
		// Frappe gives page filters a narrow column: the placeholder was cut off
		for (const f of [this.company, this.warehouse]) f.$wrapper.removeClass("col-md-2").addClass("lsh-filter");
		page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
	}

	style() {
		if (document.getElementById("lsh-style")) return;
		const css = `
.lsh { padding: 4px 0 32px; }
.page-form .lsh-filter { flex: 0 1 240px; width: 240px; max-width: 100%; min-width: 0; }
.lsh .lsh-basis { color: var(--text-muted); font-size: 12px; margin-bottom: 14px; }
.lsh .lsh-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 22px; }
.lsh .lsh-card { background: var(--card-bg, var(--fg-color)); border: 1px solid var(--border-color); border-radius: 10px; padding: 14px 16px; cursor: pointer; }
.lsh .lsh-card:hover { border-color: var(--gray-500, #8d99a6); }
.lsh .lsh-card-label { color: var(--text-muted); font-size: 13px; }
.lsh .lsh-card-count { font-size: 28px; font-weight: 600; line-height: 1.3; }
.lsh .lsh-card-note { color: var(--text-muted); font-size: 12px; }
.lsh .lsh-danger { color: var(--red-500, #e24c4c); }
.lsh .lsh-warning { color: var(--orange-500, #e79913); }
.lsh .lsh-blue { color: var(--blue-500, #1463ff); }
.lsh .lsh-muted { color: var(--text-muted); }
.lsh .lsh-box { background: var(--card-bg, var(--fg-color)); border: 1px solid var(--border-color); border-radius: 10px; padding: 14px 16px; margin-bottom: 18px; }
.lsh .lsh-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
.lsh .lsh-title { font-size: 15px; font-weight: 600; color: var(--text-color); }
.lsh .lsh-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.lsh .lsh-chip { border: 1px solid var(--border-color); background: transparent; color: var(--text-color); border-radius: 14px; padding: 2px 12px; font-size: 12px; cursor: pointer; }
.lsh .lsh-chip.active { background: var(--gray-200, #e2e6e9); border-color: var(--gray-400, #c0c6cc); }
[data-theme="dark"] .lsh .lsh-chip.active { background: var(--gray-700, #4c5a67); border-color: var(--gray-600, #687178); }
.lsh .lsh-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding: 10px 0; border-top: 1px solid var(--border-color); }
.lsh .lsh-item { flex: 1 1 220px; min-width: 0; }
.lsh .lsh-item-name { font-weight: 500; color: var(--text-color); cursor: pointer; }
.lsh .lsh-sub { color: var(--text-muted); font-size: 12px; }
.lsh .lsh-what { flex: 2 1 260px; min-width: 0; }
.lsh .lsh-when { font-weight: 600; font-size: 13px; }
.lsh .lsh-todo { font-size: 13px; color: var(--text-color); }
.lsh .lsh-act { flex: 0 0 auto; }
.lsh .lsh-empty { color: var(--text-muted); padding: 18px 0 8px; text-align: center; }
.lsh .lsh-ideas { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-bottom: 18px; }
.lsh .lsh-ideas .lsh-box { margin-bottom: 0; }
.lsh .lsh-idea { padding: 6px 0; border-top: 1px solid var(--border-color); }
.lsh .lsh-link { font-size: 12px; cursor: pointer; color: var(--blue-500, #1463ff); }
.lsh .lsh-links { display: flex; flex-wrap: wrap; gap: 8px 18px; }`;
		$('<style id="lsh-style"></style>').text(css).appendTo("head");
	}

	refresh() {
		const company = this.company.get_value();
		frappe
			.call({
				method: "lumen_shelf.restock.home.overview",
				args: { company: company || null, warehouse: this.warehouse.get_value() || null },
				freeze: !this.loaded,
			})
			.then((r) => {
				this.loaded = true;
				this.data = r.message;
				if (this.data.company && this.data.company !== company) this.company.set_value(this.data.company);
				this.render();
			});
	}

	open_report(report) {
		frappe.route_options = { company: this.data.company };
		const wh = this.data.warehouse;
		if (wh) frappe.route_options[report === "Shelf Transfers" ? "to_warehouse" : "warehouse"] = wh;
		frappe.set_route("query-report", report);
	}

	render() {
		const d = this.data;
		const e = frappe.utils.escape_html;
		const n = (x) => `<bdi dir="ltr">${e(String(x))}</bdi>`;
		const money = (v) => (v ? `<bdi>${format_currency(v, d.currency)}</bdi>` : "");
		let html = `<div class="lsh-basis">${e(d.basis)}</div><div class="lsh-cards">`;
		for (const c of d.cards) {
			const note = c.value ? money(c.value) : e(c.note || "");
			html += `<div class="lsh-card" data-report="${e(c.report)}">
				<div class="lsh-card-label">${e(c.label)}</div>
				<div class="lsh-card-count lsh-${c.count ? c.tone : "muted"}">${n(c.count)}</div>
				<div class="lsh-card-note">${note}</div></div>`;
		}
		html += `</div>`;

		const kinds = [
			["", __("All")],
			["low", __("Restock")],
			["move", __("Move between branches")],
			["expiry", __("May expire")],
			["stuck", __("Not selling")],
		].filter(([k]) => !k || d.tasks.some((t) => t.kind === k));
		if (this.kind && !kinds.some(([k]) => k === this.kind)) this.kind = "";
		const shown = d.tasks.filter((t) => !this.kind || t.kind === this.kind);
		const can_all = d.can_request && d.tasks.some((t) => t.kind === "low" && t.request);
		html += `<div class="lsh-box"><div class="lsh-head"><div class="lsh-title">${__("Today's tasks")}</div>
			${can_all ? `<button class="btn btn-primary btn-sm lsh-all">${__("Request all shortages")}</button>` : ""}</div>`;
		if (kinds.length > 2) {
			html += `<div class="lsh-chips">${kinds
				.map(([k, l]) => `<button class="lsh-chip ${k === this.kind ? "active" : ""}" data-kind="${k}">${e(l)}</button>`)
				.join("")}</div>`;
		}
		if (!shown.length) {
			html += `<div class="lsh-empty">${__("Nothing to do today. Every item is stocked.")}</div>`;
		}
		shown.forEach((t, i) => {
			const act = t.request
				? `<button class="btn btn-default btn-xs lsh-req" data-i="${d.tasks.indexOf(t)}">${__("Request this")}</button>`
				: `<button class="btn btn-default btn-xs lsh-more" data-kind="${t.kind}">${__("Details")}</button>`;
			const sub = [t.item_code !== t.item_name ? t.item_code : "", t.warehouse, t.supplier || ""].filter(Boolean);
			html += `<div class="lsh-row">
				<div class="lsh-item"><div class="lsh-item-name" data-item="${e(t.item_code)}">${e(t.item_name || t.item_code)}</div>
					<div class="lsh-sub">${sub.map(e).join(" · ")}</div></div>
				<div class="lsh-what"><div class="lsh-when lsh-${t.tone}">${e(t.when)}</div>
					<div class="lsh-todo">${e(t.todo)}${t.value ? ` <span class="lsh-sub">${money(t.value)}</span>` : ""}</div></div>
				<div class="lsh-act">${act}</div></div>`;
		});
		if (d.more_tasks) {
			html += `<div class="lsh-sub" style="padding-top: 8px">${e(
				__("And {0} more on the detail screens.", [d.more_tasks])
			)}</div>`;
		}
		html += `</div>`;

		const ideas = d.ideas.filter((b) => b.count);
		if (ideas.length) {
			html += `<div class="lsh-title" style="margin-bottom: 10px">${__("Product ideas")}</div><div class="lsh-ideas">`;
			for (const b of ideas) {
				html += `<div class="lsh-box"><div class="lsh-head"><div class="lsh-title" style="font-size: 14px">${e(b.title)}</div>
					<span class="lsh-link" data-report="${e(b.report)}">${e(__("See all ({0})", [b.count]))}</span></div>
					${b.items
						.map((x) => `<div class="lsh-idea"><div>${e(x.text)}</div><div class="lsh-sub">${e(x.note || "")}</div></div>`)
						.join("")}</div>`;
			}
			html += `</div>`;
		}

		const screens = [
			"Shelf Running Low",
			"Shelf Transfers",
			"Shelf Stock Health",
			"Shelf Promotions",
			"Shelf Forecast Accuracy",
			"Shelf Bought Together",
			"Shelf Assortment Gaps",
			"Shelf Trending Products",
		];
		html += `<div class="lsh-box"><div class="lsh-title" style="font-size: 14px; margin-bottom: 8px">${__("Detail screens")}</div>
			<div class="lsh-links">${screens.map((s) => `<span class="lsh-link" data-report="${e(s)}">${e(__(s))}</span>`).join("")}
			${d.can_settings ? `<span class="lsh-link lsh-settings">${__("Lumen Shelf Settings")}</span>` : ""}</div></div>`;

		this.$body.html(html);
		this.bind();
	}

	bind() {
		const $b = this.$body;
		const report_of = { low: "Shelf Running Low", move: "Shelf Transfers", expiry: "Shelf Stock Health", stuck: "Shelf Stock Health" };
		$b.find("[data-report]").on("click", (ev) => this.open_report($(ev.currentTarget).attr("data-report")));
		$b.find(".lsh-chip").on("click", (ev) => {
			this.kind = $(ev.currentTarget).attr("data-kind");
			this.render();
		});
		$b.find(".lsh-more").on("click", (ev) => this.open_report(report_of[$(ev.currentTarget).attr("data-kind")]));
		$b.find(".lsh-item-name").on("click", (ev) => frappe.set_route("Form", "Item", $(ev.currentTarget).attr("data-item")));
		$b.find(".lsh-settings").on("click", () => frappe.set_route("Form", "Lumen Shelf Settings"));
		$b.find(".lsh-req").on("click", (ev) => {
			const t = this.data.tasks[+$(ev.currentTarget).attr("data-i")];
			this.request(t.request.scope, Object.assign({ company: this.data.company }, t.request.filters));
		});
		$b.find(".lsh-all").on("click", () =>
			this.request("running_low", { company: this.data.company, warehouse: this.data.warehouse || "" })
		);
	}

	request(scope, filters) {
		// the same preview and create as the detail screens' button
		const call = (method) =>
			frappe.call({ method: "lumen_shelf.restock.requests." + method, args: { scope, filters }, freeze: true });
		call("preview").then((p) => {
			if (!p.message.count) return frappe.msgprint(p.message.message);
			frappe.confirm(p.message.message, () => {
				call("create").then((c) => {
					frappe.msgprint({
						title: __("Material requests"),
						message: c.message.message,
						indicator: c.message.count ? "blue" : "orange",
					});
					this.refresh();
				});
			});
		});
	}
}
