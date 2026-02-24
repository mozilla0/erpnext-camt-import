// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on("CAMT Bank Transaction", {
	refresh(frm) {
		// Bestätigungs-Buttons
		if (frm.doc.status === "Offen") {
			frm.add_custom_button(
				__("Bestätigen"),
				() => {
					frm.set_value("status", "Bestätigt");
					frm.save();
				},
				__("Aktionen")
			);

			frm.add_custom_button(
				__("Ignorieren"),
				() => {
					frm.set_value("status", "Ignoriert");
					frm.save();
				},
				__("Aktionen")
			);
		}

		if (frm.doc.status === "Bestätigt" || frm.doc.status === "Ignoriert") {
			frm.add_custom_button(
				__("Wieder öffnen"),
				() => {
					frm.set_value("status", "Offen");
					frm.save();
				}
			);
		}

		// Farbiger Indikator
		if (frm.doc.credit_debit === "CRDT") {
			frm.dashboard.set_headline(
				`<span class="text-success" style="font-size: 1.2em;">
					<i class="fa fa-arrow-down"></i>
					+${format_currency(frm.doc.amount, frm.doc.currency)} ${frm.doc.currency}
					<small>(Zahlungseingang)</small>
				</span>`
			);
		} else if (frm.doc.credit_debit === "DBIT") {
			frm.dashboard.set_headline(
				`<span class="text-danger" style="font-size: 1.2em;">
					<i class="fa fa-arrow-up"></i>
					-${format_currency(frm.doc.amount, frm.doc.currency)} ${frm.doc.currency}
					<small>(Zahlungsausgang)</small>
				</span>`
			);
		}
	},
});
