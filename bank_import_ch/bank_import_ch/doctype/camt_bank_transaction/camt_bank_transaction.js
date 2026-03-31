// CAMT Bank Transaction – Form Script
// Erweitert um: QRR-Matching, manuelle Rechnungszuordnung, Payment Entry, Journal Entry

frappe.ui.form.on("CAMT Bank Transaction", {
	refresh(frm) {
		// ─── Farbiger Betrag-Indikator ───
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

		// ─── Status-Buttons ───
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
			frm.add_custom_button(__("Wieder öffnen"), () => {
				frm.set_value("status", "Offen");
				frm.set_value("confirmed_by", "");
				frm.set_value("confirmed_at", "");
				frm.save();
			});
		}

		// ─── Matching-Buttons ───
		let match_status = frm.doc.match_status || "Offen";

		if (match_status === "Offen" || match_status === "") {
			// QRR Auto-Match (nur bei Gutschriften mit Referenz)
			if (frm.doc.credit_debit === "CRDT" && frm.doc.creditor_reference) {
				frm.add_custom_button(
					__("QRR-Referenz suchen"),
					() => camt_match_qrr(frm),
					__("Zuordnung")
				);
			}

			// Manuelle Zuordnung
			if (frm.doc.credit_debit === "CRDT") {
				frm.add_custom_button(
					__("Sales Invoice zuordnen"),
					() => camt_assign_invoice(frm, "Sales Invoice"),
					__("Zuordnung")
				);
			}
			if (frm.doc.credit_debit === "DBIT") {
				frm.add_custom_button(
					__("Purchase Invoice zuordnen"),
					() => camt_assign_invoice(frm, "Purchase Invoice"),
					__("Zuordnung")
				);
			}
		}

		if (match_status === "Zugeordnet") {
			// Zuordnung aufheben
			frm.add_custom_button(
				__("Zuordnung aufheben"),
				() => camt_unassign(frm),
				__("Zuordnung")
			);

			// Payment Entry erstellen
			if (!frm.doc.payment_entry) {
				frm.add_custom_button(
					__("Payment Entry erstellen"),
					() => camt_create_payment_entry(frm),
					__("Buchen")
				);
			}
		}

		// Journal Entry (immer verfügbar wenn noch nicht gebucht)
		if (!frm.doc.journal_entry && match_status !== "Gebucht") {
			frm.add_custom_button(
				__("Journal Entry erstellen"),
				() => camt_create_journal_entry(frm),
				__("Buchen")
			);
		}

		// ─── Links zu erstellten Buchungen ───
		if (frm.doc.payment_entry) {
			frm.dashboard.add_comment(
				__("Payment Entry: ") +
				`<a href="/app/payment-entry/${frm.doc.payment_entry}">${frm.doc.payment_entry}</a>`
			);
		}
		if (frm.doc.journal_entry) {
			frm.dashboard.add_comment(
				__("Journal Entry: ") +
				`<a href="/app/journal-entry/${frm.doc.journal_entry}">${frm.doc.journal_entry}</a>`
			);
		}
	},

	matched_invoice(frm) {
		// Party automatisch setzen wenn Rechnung manuell geändert wird
		if (frm.doc.matched_invoice && frm.doc.matched_invoice_type) {
			frappe.db.get_value(
				frm.doc.matched_invoice_type,
				frm.doc.matched_invoice,
				frm.doc.matched_invoice_type === "Sales Invoice" ? "customer" : "supplier",
				(r) => {
					if (r) {
						let party = r.customer || r.supplier;
						frm.set_value("matched_party_type", r.customer ? "Customer" : "Supplier");
						frm.set_value("matched_party", party);
					}
				}
			);
		}
	},
});


// ─── QRR Auto-Match ───
function camt_match_qrr(frm) {
	frappe.call({
		method: "bank_import_ch.bank_import_ch.api.match_invoice_by_qrr",
		args: { transaction_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Suche nach QRR-Referenz..."),
		callback(r) {
			if (!r.message) return;
			let result = r.message;

			if (result.status === "matched") {
				frappe.show_alert({
					message: result.message,
					indicator: "green",
				});
				frm.reload_doc();
			} else if (result.status === "multiple") {
				// Dialog mit Auswahl
				let options = result.invoices.map(
					(inv) => `${inv.name} | ${inv.customer_name} (offen: ${format_currency(inv.outstanding_amount, inv.currency)})`
				);
				frappe.prompt(
					{
						label: __("Rechnung auswählen"),
						fieldname: "invoice",
						fieldtype: "Select",
						options: options,
						reqd: 1,
					},
					(values) => {
						let selected_name = values.invoice.split(" | ")[0];
						frappe.call({
							method: "bank_import_ch.bank_import_ch.api.assign_invoice",
							args: {
								transaction_name: frm.doc.name,
								invoice_type: "Sales Invoice",
								invoice_name: selected_name,
							},
							callback() {
								frm.reload_doc();
							},
						});
					},
					__("Mehrere Rechnungen gefunden"),
					__("Zuordnen")
				);
			} else {
				frappe.show_alert({
					message: result.message,
					indicator: "orange",
				});
			}
		},
	});
}


// ─── Manuelle Rechnung zuordnen ───
function camt_assign_invoice(frm, invoice_type) {
	let d = new frappe.ui.Dialog({
		title: __(invoice_type === "Sales Invoice" ? "Sales Invoice zuordnen" : "Purchase Invoice zuordnen"),
		fields: [
			{
				label: __("Rechnung"),
				fieldname: "invoice",
				fieldtype: "Link",
				options: invoice_type,
				reqd: 1,
				get_query() {
					return {
						filters: {
							docstatus: 1,
							outstanding_amount: [">", 0],
						},
					};
				},
			},
		],
		primary_action_label: __("Zuordnen"),
		primary_action(values) {
			frappe.call({
				method: "bank_import_ch.bank_import_ch.api.assign_invoice",
				args: {
					transaction_name: frm.doc.name,
					invoice_type: invoice_type,
					invoice_name: values.invoice,
				},
				callback(r) {
					d.hide();
					if (r.message && r.message.status === "ok") {
						frappe.show_alert({
							message: r.message.message,
							indicator: "green",
						});
						frm.reload_doc();
					}
				},
			});
		},
	});
	d.show();
}


// ─── Zuordnung aufheben ───
function camt_unassign(frm) {
	frappe.confirm(
		__("Zuordnung zu {0} aufheben?").replace("{0}", frm.doc.matched_invoice),
		() => {
			frappe.call({
				method: "bank_import_ch.bank_import_ch.api.unassign_invoice",
				args: { transaction_name: frm.doc.name },
				callback() {
					frm.reload_doc();
				},
			});
		}
	);
}


// ─── Payment Entry erstellen ───
function camt_create_payment_entry(frm) {
	// ERPNext Standard get_payment_entry nutzen – erstellt einen vorausgefüllten PE
	// und öffnet das Standard-Formular, wo der User prüfen und buchen kann
	frappe.call({
		method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
		args: {
			dt: frm.doc.matched_invoice_type,
			dn: frm.doc.matched_invoice,
		},
		freeze: true,
		freeze_message: __("Payment Entry wird vorbereitet..."),
		callback(r) {
			if (!r.message) return;

			let pe = r.message;

			// CAMT-Daten überschreiben
			pe.posting_date = frm.doc.booking_date;
			pe.reference_no = frm.doc.account_service_reference
				|| frm.doc.creditor_reference
				|| frm.doc.transaction_id
				|| frm.doc.name;
			pe.reference_date = frm.doc.booking_date;
			pe.remarks = (frm.doc.additional_info || frm.doc.remittance_info || "")
				+ " (CAMT: " + frm.doc.name + ")";
			pe.camt_bank_transaction = frm.doc.name;

			// Betrag aus CAMT setzen
			if (pe.payment_type === "Receive") {
				pe.paid_amount = frm.doc.amount;
				pe.received_amount = frm.doc.amount;
			} else {
				pe.paid_amount = frm.doc.amount;
				pe.received_amount = frm.doc.amount;
			}

			// Allocated Amount anpassen
			if (pe.references && pe.references.length > 0) {
				pe.references[0].allocated_amount = frm.doc.amount;
			}

			// Standard Payment Entry Formular öffnen
			frappe.model.with_doctype("Payment Entry", () => {
				let doc = frappe.model.sync(pe);
				frappe.set_route("Form", "Payment Entry", doc[0].name);
			});
		},
	});
}


// ─── Journal Entry erstellen ───
function camt_create_journal_entry(frm) {
	let company =
		frappe.defaults.get_user_default("Company") ||
		frappe.defaults.get_global_default("company");

	// Direkt ein neues Journal Entry Formular öffnen mit vorausgefüllten Daten
	let amount = frm.doc.amount;
	let remark = (frm.doc.additional_info || frm.doc.remittance_info || "")
		+ " (CAMT: " + frm.doc.name + ")";

	frappe.new_doc("Journal Entry", {
		voucher_type: "Bank Entry",
		posting_date: frm.doc.booking_date,
		company: company,
		user_remark: remark,
		cheque_no: frm.doc.account_service_reference || frm.doc.transaction_id || frm.doc.name,
		cheque_date: frm.doc.booking_date,
		camt_bank_transaction: frm.doc.name,
	});
}
