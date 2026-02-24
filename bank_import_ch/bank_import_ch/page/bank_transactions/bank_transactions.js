// Banktransaktionen CH – Übersichtsseite
// Zeigt alle importierten CAMT-Transaktionen in einer übersichtlichen Listenansicht
// mit Möglichkeit zur Bestätigung einzelner oder mehrerer Transaktionen.

frappe.pages["bank-transactions-ch"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Banktransaktionen"),
		single_column: true,
	});

	page.main.addClass("bank-transactions-ch-page");

	// State
	const state = {
		transactions: [],
		total_count: 0,
		page_length: 50,
		start: 0,
		filters: {
			status: "",
			camt_import: "",
			credit_debit: "",
			from_date: "",
			to_date: "",
			search: "",
			hide_confirmed: true,
		},
		selected: new Set(),
		loading: false,
	};

	// === TOOLBAR ===
	page.set_primary_action(__("Importieren"), () => {
		frappe.new_doc("CAMT Import");
	}, "fa fa-upload");

	page.set_secondary_action(__("Aktualisieren"), () => {
		load_transactions();
	}, "fa fa-refresh");

	// === FILTER BAR ===
	const $filter_bar = $(`
		<div class="bank-txn-filters">
			<div class="filter-row">
				<div class="filter-group">
					<label>${__("Status")}</label>
					<select class="form-control input-sm" data-filter="status">
						<option value="">${__("Alle")}</option>
						<option value="Offen" selected>${__("Offen")}</option>
						<option value="Bestätigt">${__("Bestätigt")}</option>
						<option value="Ignoriert">${__("Ignoriert")}</option>
					</select>
				</div>
				<div class="filter-group">
					<label>${__("Import")}</label>
					<input class="form-control input-sm" data-filter="camt_import"
						placeholder="${__("CAMT Import...")}">
				</div>
				<div class="filter-group">
					<label>${__("Art")}</label>
					<select class="form-control input-sm" data-filter="credit_debit">
						<option value="">${__("Alle")}</option>
						<option value="CRDT">${__("Zahlungseingang")}</option>
						<option value="DBIT">${__("Zahlungsausgang")}</option>
					</select>
				</div>
				<div class="filter-group">
					<label>${__("Von")}</label>
					<input type="date" class="form-control input-sm" data-filter="from_date">
				</div>
				<div class="filter-group">
					<label>${__("Bis")}</label>
					<input type="date" class="form-control input-sm" data-filter="to_date">
				</div>
				<div class="filter-group filter-search">
					<label>${__("Suche")}</label>
					<input class="form-control input-sm" data-filter="search"
						placeholder="${__("Name, IBAN, Referenz...")}">
				</div>
			</div>
			<div class="filter-row filter-actions">
				<label class="hide-confirmed-toggle">
					<input type="checkbox" id="hide-confirmed" checked>
					${__("Bestätigte ausblenden")}
				</label>
			</div>
		</div>
	`).appendTo(page.main);

	// Filter-Events
	$filter_bar.find("[data-filter]").on("change", function () {
		const key = $(this).data("filter");
		state.filters[key] = $(this).val();
		state.start = 0;
		load_transactions();
	});

	$filter_bar.find("[data-filter='search']").on("input", frappe.utils.debounce(function () {
		state.filters.search = $(this).val();
		state.start = 0;
		load_transactions();
	}, 400));

	$filter_bar.find("#hide-confirmed").on("change", function () {
		state.filters.hide_confirmed = $(this).is(":checked");
		state.start = 0;
		load_transactions();
	});

	// === SUMMARY BAR ===
	const $summary = $(`<div class="bank-txn-summary"></div>`).appendTo(page.main);

	// === ACTIONS BAR ===
	const $actions = $(`
		<div class="bank-txn-actions" style="display:none;">
			<div class="selection-info">
				<span class="selected-count">0</span> ${__("ausgewählt")}
			</div>
			<button class="btn btn-success btn-sm btn-confirm-selected">
				<i class="fa fa-check"></i> ${__("Bestätigen")}
			</button>
			<button class="btn btn-secondary btn-sm btn-ignore-selected">
				<i class="fa fa-eye-slash"></i> ${__("Ignorieren")}
			</button>
			<button class="btn btn-default btn-sm btn-deselect-all">
				${__("Auswahl aufheben")}
			</button>
		</div>
	`).appendTo(page.main);

	$actions.find(".btn-confirm-selected").on("click", () => {
		confirm_selected();
	});

	$actions.find(".btn-ignore-selected").on("click", () => {
		ignore_selected();
	});

	$actions.find(".btn-deselect-all").on("click", () => {
		state.selected.clear();
		update_selection_ui();
	});

	// === TABLE ===
	const $table_wrapper = $(`
		<div class="bank-txn-table-wrapper">
			<table class="bank-txn-table">
				<thead>
					<tr>
						<th class="col-check">
							<input type="checkbox" class="select-all-check">
						</th>
						<th class="col-status">${__("Status")}</th>
						<th class="col-date">${__("Buchungsdatum")}</th>
						<th class="col-name">${__("Gegenpartei")}</th>
						<th class="col-description">${__("Beschreibung")}</th>
						<th class="col-type">${__("Art")}</th>
						<th class="col-amount">${__("Betrag")}</th>
						<th class="col-actions"></th>
					</tr>
				</thead>
				<tbody class="bank-txn-body">
				</tbody>
			</table>
			<div class="bank-txn-empty" style="display:none;">
				<div class="empty-state">
					<i class="fa fa-inbox fa-3x text-muted"></i>
					<p class="text-muted mt-3">${__("Keine Transaktionen gefunden")}</p>
					<button class="btn btn-primary btn-sm mt-2" onclick="frappe.new_doc('CAMT Import')">
						${__("CAMT.053 importieren")}
					</button>
				</div>
			</div>
		</div>
	`).appendTo(page.main);

	// Select All
	$table_wrapper.find(".select-all-check").on("change", function () {
		const checked = $(this).is(":checked");
		state.transactions.forEach((txn) => {
			if (txn.status === "Offen") {
				if (checked) {
					state.selected.add(txn.name);
				} else {
					state.selected.delete(txn.name);
				}
			}
		});
		update_selection_ui();
	});

	// === PAGINATION ===
	const $pagination = $(`
		<div class="bank-txn-pagination">
			<div class="pagination-info"></div>
			<div class="pagination-buttons">
				<button class="btn btn-default btn-sm btn-prev" disabled>
					<i class="fa fa-chevron-left"></i> ${__("Zurück")}
				</button>
				<button class="btn btn-default btn-sm btn-next">
					${__("Weiter")} <i class="fa fa-chevron-right"></i>
				</button>
			</div>
		</div>
	`).appendTo(page.main);

	$pagination.find(".btn-prev").on("click", () => {
		if (state.start > 0) {
			state.start = Math.max(0, state.start - state.page_length);
			load_transactions();
		}
	});

	$pagination.find(".btn-next").on("click", () => {
		if (state.start + state.page_length < state.total_count) {
			state.start += state.page_length;
			load_transactions();
		}
	});

	// === RENDER FUNCTIONS ===

	function render_summary(data) {
		const summary = data || {};
		$summary.html(`
			<div class="summary-cards">
				<div class="summary-card">
					<span class="summary-label">${__("Total")}</span>
					<span class="summary-value">${summary.total_count || 0}</span>
				</div>
				<div class="summary-card card-open">
					<span class="summary-label">${__("Offen")}</span>
					<span class="summary-value">${count_by_status("Offen")}</span>
				</div>
				<div class="summary-card card-confirmed">
					<span class="summary-label">${__("Bestätigt")}</span>
					<span class="summary-value">${count_by_status("Bestätigt")}</span>
				</div>
			</div>
		`);
	}

	function count_by_status(status) {
		// Wir verwenden die aktuelle Filterung, daher ist dies eine Approximation
		return state.transactions.filter((t) => t.status === status).length;
	}

	function render_transactions() {
		const $body = $table_wrapper.find(".bank-txn-body");
		$body.empty();

		if (!state.transactions.length) {
			$table_wrapper.find(".bank-txn-table").hide();
			$table_wrapper.find(".bank-txn-empty").show();
			return;
		}

		$table_wrapper.find(".bank-txn-table").show();
		$table_wrapper.find(".bank-txn-empty").hide();

		state.transactions.forEach((txn) => {
			const is_credit = txn.credit_debit === "CRDT";
			const amount_class = is_credit ? "amount-credit" : "amount-debit";
			const amount_prefix = is_credit ? "+" : "-";
			const type_label = is_credit ? __("Zahlungseingang") : __("Zahlungsausgang");
			const type_class = is_credit ? "type-credit" : "type-debit";
			const status_class = `status-${txn.status.toLowerCase()}`;
			const is_selected = state.selected.has(txn.name);
			const is_open = txn.status === "Offen";

			const description = txn.remittance_info || txn.additional_info || "";
			const truncated_desc =
				description.length > 80
					? description.substring(0, 80) + "..."
					: description;

			const $row = $(`
				<tr class="txn-row ${status_class} ${is_selected ? "row-selected" : ""}"
					data-name="${txn.name}">
					<td class="col-check">
						<input type="checkbox" class="txn-check"
							data-name="${txn.name}"
							${is_selected ? "checked" : ""}
							${!is_open ? "disabled" : ""}>
					</td>
					<td class="col-status">
						<span class="status-badge ${status_class}">
							${txn.status}
						</span>
					</td>
					<td class="col-date">
						${frappe.datetime.str_to_user(txn.booking_date) || "-"}
					</td>
					<td class="col-name">
						<div class="counterparty-name">${frappe.utils.escape_html(txn.counterparty_name || "-")}</div>
						${txn.counterparty_iban
							? `<div class="counterparty-iban text-muted small">${txn.counterparty_iban}</div>`
							: ""
						}
					</td>
					<td class="col-description">
						<div class="description-text" title="${frappe.utils.escape_html(description)}">
							${frappe.utils.escape_html(truncated_desc)}
						</div>
					</td>
					<td class="col-type">
						<span class="type-badge ${type_class}">${type_label}</span>
					</td>
					<td class="col-amount">
						<span class="${amount_class}">
							${amount_prefix}${format_currency(Math.abs(txn.signed_amount), txn.currency)} ${txn.currency}
						</span>
					</td>
					<td class="col-actions">
						${is_open ? `
							<button class="btn btn-xs btn-success btn-confirm-one"
								data-name="${txn.name}"
								title="${__("Bestätigen")}">
								<i class="fa fa-check"></i>
							</button>
							<button class="btn btn-xs btn-default btn-ignore-one"
								data-name="${txn.name}"
								title="${__("Ignorieren")}">
								<i class="fa fa-eye-slash"></i>
							</button>
						` : `
							<button class="btn btn-xs btn-default btn-reopen-one"
								data-name="${txn.name}"
								title="${__("Wieder öffnen")}">
								<i class="fa fa-undo"></i>
							</button>
						`}
						<button class="btn btn-xs btn-default btn-detail"
							data-name="${txn.name}"
							title="${__("Details")}">
							<i class="fa fa-expand"></i>
						</button>
					</td>
				</tr>
			`);

			$body.append($row);
		});

		// Row Events
		$body.find(".txn-check").on("change", function () {
			const name = $(this).data("name");
			if ($(this).is(":checked")) {
				state.selected.add(name);
			} else {
				state.selected.delete(name);
			}
			update_selection_ui();
		});

		$body.find(".btn-confirm-one").on("click", function (e) {
			e.stopPropagation();
			confirm_single($(this).data("name"));
		});

		$body.find(".btn-ignore-one").on("click", function (e) {
			e.stopPropagation();
			ignore_single($(this).data("name"));
		});

		$body.find(".btn-reopen-one").on("click", function (e) {
			e.stopPropagation();
			reopen_single($(this).data("name"));
		});

		$body.find(".btn-detail").on("click", function (e) {
			e.stopPropagation();
			frappe.set_route("Form", "CAMT Bank Transaction", $(this).data("name"));
		});

		// Klick auf Zeile → Details
		$body.find(".txn-row").on("click", function (e) {
			if ($(e.target).is("input, button, i, .btn")) return;
			const name = $(this).data("name");
			show_detail_panel(name);
		});

		// Pagination
		const current_page = Math.floor(state.start / state.page_length) + 1;
		const total_pages = Math.ceil(state.total_count / state.page_length);
		$pagination.find(".pagination-info").text(
			__("{0}–{1} von {2}", [
				state.start + 1,
				Math.min(state.start + state.page_length, state.total_count),
				state.total_count,
			])
		);
		$pagination.find(".btn-prev").prop("disabled", state.start === 0);
		$pagination.find(".btn-next").prop(
			"disabled",
			state.start + state.page_length >= state.total_count
		);
	}

	function update_selection_ui() {
		const count = state.selected.size;
		$actions.toggle(count > 0);
		$actions.find(".selected-count").text(count);

		// Checkboxen synchronisieren
		$table_wrapper.find(".txn-check").each(function () {
			const name = $(this).data("name");
			$(this).prop("checked", state.selected.has(name));
		});

		// Zeilen hervorheben
		$table_wrapper.find(".txn-row").each(function () {
			const name = $(this).data("name");
			$(this).toggleClass("row-selected", state.selected.has(name));
		});
	}

	// === DETAIL PANEL ===
	function show_detail_panel(txn_name) {
		const txn = state.transactions.find((t) => t.name === txn_name);
		if (!txn) return;

		const is_credit = txn.credit_debit === "CRDT";
		const amount_class = is_credit ? "amount-credit" : "amount-debit";
		const amount_prefix = is_credit ? "+" : "-";

		const d = new frappe.ui.Dialog({
			title: `${txn.counterparty_name || __("Transaktion")} – ${txn.name}`,
			size: "large",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "detail_html",
				},
			],
		});

		const html = `
			<div class="txn-detail-panel">
				<div class="detail-header">
					<div class="detail-amount ${amount_class}">
						${amount_prefix}${format_currency(Math.abs(txn.signed_amount), txn.currency)} ${txn.currency}
					</div>
					<span class="status-badge status-${txn.status.toLowerCase()}">${txn.status}</span>
				</div>

				<div class="detail-grid">
					<div class="detail-section">
						<h6>${__("Gegenpartei")}</h6>
						<div class="detail-field">
							<label>${__("Name")}</label>
							<span>${txn.counterparty_name || "-"}</span>
						</div>
						<div class="detail-field">
							<label>${__("IBAN")}</label>
							<span>${txn.counterparty_iban || "-"}</span>
						</div>
					</div>

					<div class="detail-section">
						<h6>${__("Daten")}</h6>
						<div class="detail-field">
							<label>${__("Buchungsdatum")}</label>
							<span>${frappe.datetime.str_to_user(txn.booking_date) || "-"}</span>
						</div>
						<div class="detail-field">
							<label>${__("Valutadatum")}</label>
							<span>${frappe.datetime.str_to_user(txn.value_date) || "-"}</span>
						</div>
					</div>

					<div class="detail-section full-width">
						<h6>${__("Beschreibung")}</h6>
						<div class="detail-field">
							<label>${__("Verwendungszweck")}</label>
							<span>${txn.remittance_info || "-"}</span>
						</div>
						<div class="detail-field">
							<label>${__("Zusatzinfo")}</label>
							<span>${txn.additional_info || "-"}</span>
						</div>
						${txn.creditor_reference ? `
						<div class="detail-field">
							<label>${__("Referenz")}</label>
							<span>${txn.creditor_reference}</span>
						</div>
						` : ""}
						${txn.end_to_end_id ? `
						<div class="detail-field">
							<label>${__("End-to-End ID")}</label>
							<span>${txn.end_to_end_id}</span>
						</div>
						` : ""}
					</div>
				</div>
			</div>
		`;

		d.fields_dict.detail_html.$wrapper.html(html);

		if (txn.status === "Offen") {
			d.set_primary_action(__("Bestätigen"), () => {
				confirm_single(txn.name);
				d.hide();
			});
			d.set_secondary_action_label(__("Ignorieren"));
			d.set_secondary_action(() => {
				ignore_single(txn.name);
				d.hide();
			});
		}

		d.$wrapper.find(".btn-modal-close").before(
			`<a class="btn btn-default btn-sm" href="/app/camt-bank-transaction/${txn.name}"
				style="margin-right: 8px;">
				${__("Formular öffnen")}
			</a>`
		);

		d.show();
	}

	// === API CALLS ===

	function load_transactions() {
		if (state.loading) return;
		state.loading = true;

		frappe.call({
			method: "bank_import_ch.bank_import_ch.api.get_bank_transactions_page",
			args: {
				start: state.start,
				page_length: state.page_length,
				status: state.filters.status,
				camt_import: state.filters.camt_import,
				credit_debit: state.filters.credit_debit,
				from_date: state.filters.from_date,
				to_date: state.filters.to_date,
				search: state.filters.search,
				hide_confirmed: state.filters.hide_confirmed,
			},
			callback(r) {
				state.loading = false;
				if (r.message) {
					state.transactions = r.message.transactions || [];
					state.total_count = r.message.total_count || 0;
					render_summary(r.message);
					render_transactions();
				}
			},
			error() {
				state.loading = false;
			},
		});
	}

	function confirm_single(name) {
		frappe.call({
			method: "bank_import_ch.bank_import_ch.api.confirm_transactions",
			args: { transaction_names: JSON.stringify([name]) },
			callback() {
				state.selected.delete(name);
				load_transactions();
				frappe.show_alert({ message: __("Transaktion bestätigt"), indicator: "green" });
			},
		});
	}

	function ignore_single(name) {
		frappe.call({
			method: "bank_import_ch.bank_import_ch.api.ignore_transactions",
			args: { transaction_names: JSON.stringify([name]) },
			callback() {
				state.selected.delete(name);
				load_transactions();
				frappe.show_alert({ message: __("Transaktion ignoriert"), indicator: "grey" });
			},
		});
	}

	function reopen_single(name) {
		frappe.call({
			method: "bank_import_ch.bank_import_ch.api.reopen_transaction",
			args: { transaction_name: name },
			callback() {
				load_transactions();
				frappe.show_alert({ message: __("Transaktion wieder geöffnet"), indicator: "blue" });
			},
		});
	}

	function confirm_selected() {
		const names = Array.from(state.selected);
		if (!names.length) return;

		frappe.confirm(
			__("{0} Transaktionen bestätigen?", [names.length]),
			() => {
				frappe.call({
					method: "bank_import_ch.bank_import_ch.api.confirm_transactions",
					args: { transaction_names: JSON.stringify(names) },
					callback(r) {
						state.selected.clear();
						load_transactions();
						if (r.message) frappe.msgprint(r.message);
					},
				});
			}
		);
	}

	function ignore_selected() {
		const names = Array.from(state.selected);
		if (!names.length) return;

		frappe.confirm(
			__("{0} Transaktionen ignorieren?", [names.length]),
			() => {
				frappe.call({
					method: "bank_import_ch.bank_import_ch.api.ignore_transactions",
					args: { transaction_names: JSON.stringify(names) },
					callback(r) {
						state.selected.clear();
						load_transactions();
						if (r.message) frappe.msgprint(r.message);
					},
				});
			}
		);
	}

	// === INIT ===
	// Status-Filter initial auf "Offen" setzen
	state.filters.status = "Offen";
	load_transactions();
};
