// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on("CAMT Import", {
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
