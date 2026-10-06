// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on("CAMT Import", {
	camt_file(frm) {
		// Sobald eine Datei hochgeladen wird: IBAN extrahieren und Bankkonto vorbelegen
		if (frm.doc.camt_file && !frm.doc.message_id) {
			frappe.call({
				method: "bank_import_ch.bank_import_ch.api.preview_camt_file",
				args: { file_url: frm.doc.camt_file },
				callback(r) {
					if (!r.message) return;
					let data = r.message;

					if (data.account_iban) {
						frm.set_value("account_iban", data.account_iban);
					}
					if (data.account_owner) {
						frm.set_value("account_owner", data.account_owner);
					}
					if (data.account_currency) {
						frm.set_value("account_currency", data.account_currency);
					}
					if (data.bank_account) {
						frm.set_value("bank_account", data.bank_account);
						frappe.show_alert({
							message: __("Bankkonto automatisch erkannt: {0}").replace("{0}", data.bank_account),
							indicator: "green",
						});
					} else if (data.account_iban) {
						frappe.show_alert({
							message: __("IBAN {0} erkannt – kein passendes Bankkonto gefunden. Bitte manuell auswählen.").replace("{0}", data.account_iban),
							indicator: "orange",
						});
					}
				},
			});
		}
	},

	refresh(frm) {
		if (frm.doc.status === "Importiert" || frm.doc.status === "Teilweise bestätigt") {
			frm.add_custom_button(
				__("Transaktionen anzeigen"),
				() => {
					frappe.set_route("List", "CAMT Bank Transaction", {
						camt_import: frm.doc.name,
					});
				},
				__("Aktionen")
			);

			frm.add_custom_button(
				__("QRR Auto-Matching"),
				() => {
					frappe.call({
						method: "bank_import_ch.bank_import_ch.api.match_all_by_qrr",
						args: { camt_import: frm.doc.name },
						freeze: true,
						freeze_message: __("QRR-Referenzen werden abgeglichen..."),
						callback(r) {
							if (r.message) {
								frappe.msgprint({
									title: __("Auto-Matching Ergebnis"),
									indicator: r.message.matched > 0 ? "green" : "orange",
									message: r.message.message,
								});
								frm.reload_doc();
							}
						},
					});
				},
				__("Aktionen")
			);

			frm.add_custom_button(
				__("Alle bestätigen"),
				() => {
					frappe.confirm(
						__("Möchten Sie wirklich alle offenen Transaktionen bestätigen?"),
						() => {
							frappe.call({
								method: "bank_import_ch.bank_import_ch.api.confirm_all_transactions",
								args: { camt_import: frm.doc.name },
								callback(r) {
									if (r.message) {
										frappe.msgprint(r.message);
										frm.reload_doc();
									}
								},
							});
						}
					);
				},
				__("Aktionen")
			);
		}

		// Zusammenfassung aktualisieren
		if (frm.doc.name && !frm.is_new()) {
			frm.add_custom_button(
				__("Status aktualisieren"),
				() => {
					frappe.call({
						method: "bank_import_ch.bank_import_ch.api.update_import_summary",
						args: { camt_import: frm.doc.name },
						callback() {
							frm.reload_doc();
						},
					});
				}
			);
		}

		// Farbige Status-Anzeige
		if (frm.doc.status === "Vollständig bestätigt") {
			frm.dashboard.set_headline(
				`<span class="text-success">
					<i class="fa fa-check-circle"></i> Alle Transaktionen bestätigt
				</span>`
			);
		} else if (frm.doc.status === "Teilweise bestätigt") {
			frm.dashboard.set_headline(
				`<span class="text-warning">
					<i class="fa fa-clock-o"></i>
					${frm.doc.pending_transactions} offene Transaktionen
				</span>`
			);
		}
	},
});
