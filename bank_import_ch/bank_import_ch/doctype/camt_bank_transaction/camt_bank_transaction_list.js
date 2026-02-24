// List View Einstellungen für CAMT Bank Transaction
// Zeigt farbige Indikatoren für Zahlungsein-/ausgänge

frappe.listview_settings["CAMT Bank Transaction"] = {
	add_fields: ["status", "credit_debit", "signed_amount", "currency", "counterparty_name"],

	get_indicator(doc) {
		if (doc.status === "Bestätigt") {
			return [__("Bestätigt"), "green", "status,=,Bestätigt"];
		}
		if (doc.status === "Ignoriert") {
			return [__("Ignoriert"), "grey", "status,=,Ignoriert"];
		}
		if (doc.credit_debit === "CRDT") {
			return [__("Eingang"), "blue", "credit_debit,=,CRDT"];
		}
		if (doc.credit_debit === "DBIT") {
			return [__("Ausgang"), "orange", "credit_debit,=,DBIT"];
		}
		return [__("Offen"), "yellow", "status,=,Offen"];
	},

	formatters: {
		signed_amount(value, df, doc) {
			if (flt(value) > 0) {
				return `<span class="text-success font-weight-bold">
					+${format_currency(Math.abs(value), doc.currency)}
				</span>`;
			} else if (flt(value) < 0) {
				return `<span class="text-danger font-weight-bold">
					-${format_currency(Math.abs(value), doc.currency)}
				</span>`;
			}
			return format_currency(value, doc.currency);
		},
	},

	onload(listview) {
		// Schnelle Filter hinzufügen
		listview.page.add_inner_button(__("Nur offene"), () => {
			listview.filter_area.add([[listview.doctype, "status", "=", "Offen"]]);
		});

		// Massen-Bestätigung
		listview.page.add_action_item(__("Ausgewählte bestätigen"), () => {
			const selected = listview.get_checked_items();
			if (!selected.length) {
				frappe.msgprint(__("Bitte wählen Sie mindestens eine Transaktion aus."));
				return;
			}

			frappe.call({
				method: "bank_import_ch.bank_import_ch.api.confirm_transactions",
				args: {
					transaction_names: selected.map((d) => d.name),
				},
				callback(r) {
					if (r.message) {
						frappe.msgprint(r.message);
						listview.refresh();
					}
				},
			});
		});
	},
};
