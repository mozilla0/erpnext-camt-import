"""API-Endpunkte für Bank Import CH.

Enthält alle whitelisted Methoden, die vom Frontend aufgerufen werden.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, cint


@frappe.whitelist()
def confirm_transactions(transaction_names):
	"""Mehrere Transaktionen auf einmal bestätigen."""
	if isinstance(transaction_names, str):
		import json
		transaction_names = json.loads(transaction_names)

	count = 0
	for name in transaction_names:
		doc = frappe.get_doc("CAMT Bank Transaction", name)
		if doc.status == "Offen":
			doc.status = "Bestätigt"
			doc.confirmed_by = frappe.session.user
			doc.confirmed_at = now_datetime()
			doc.save(ignore_permissions=True)
			count += 1

	frappe.db.commit()

	# Import-Zusammenfassungen aktualisieren
	imports = set()
	for name in transaction_names:
		imp = frappe.db.get_value("CAMT Bank Transaction", name, "camt_import")
		if imp:
			imports.add(imp)

	for imp_name in imports:
		try:
			imp_doc = frappe.get_doc("CAMT Import", imp_name)
			imp_doc.update_summary()
		except Exception:
			pass

	return _("{0} Transaktionen bestätigt.").format(count)


@frappe.whitelist()
def confirm_all_transactions(camt_import):
	"""Alle offenen Transaktionen eines Imports bestätigen."""
	txns = frappe.get_all(
		"CAMT Bank Transaction",
		filters={"camt_import": camt_import, "status": "Offen"},
		pluck="name",
	)

	for name in txns:
		frappe.db.set_value(
			"CAMT Bank Transaction",
			name,
			{
				"status": "Bestätigt",
				"confirmed_by": frappe.session.user,
				"confirmed_at": now_datetime(),
			},
		)

	frappe.db.commit()

	# Import aktualisieren
	imp_doc = frappe.get_doc("CAMT Import", camt_import)
	imp_doc.update_summary()

	return _("{0} Transaktionen bestätigt.").format(len(txns))


@frappe.whitelist()
def ignore_transactions(transaction_names):
	"""Mehrere Transaktionen ignorieren."""
	if isinstance(transaction_names, str):
		import json
		transaction_names = json.loads(transaction_names)

	count = 0
	for name in transaction_names:
		doc = frappe.get_doc("CAMT Bank Transaction", name)
		if doc.status == "Offen":
			doc.status = "Ignoriert"
			doc.save(ignore_permissions=True)
			count += 1

	frappe.db.commit()
	return _("{0} Transaktionen ignoriert.").format(count)


@frappe.whitelist()
def reopen_transaction(transaction_name):
	"""Eine bestätigte/ignorierte Transaktion wieder öffnen."""
	doc = frappe.get_doc("CAMT Bank Transaction", transaction_name)
	doc.status = "Offen"
	doc.confirmed_by = ""
	doc.confirmed_at = None
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return _("Transaktion wieder geöffnet.")


@frappe.whitelist()
def update_import_summary(camt_import):
	"""Import-Zusammenfassung manuell aktualisieren."""
	doc = frappe.get_doc("CAMT Import", camt_import)
	doc.update_summary()
	return _("Zusammenfassung aktualisiert.")


@frappe.whitelist()
def get_transaction_summary(camt_import=None, bank_account=None):
	"""Zusammenfassung der Transaktionen abrufen."""
	filters = {}
	if camt_import:
		filters["camt_import"] = camt_import
	if bank_account:
		filters["bank_account"] = bank_account

	total = frappe.db.count("CAMT Bank Transaction", filters)

	filters_open = {**filters, "status": "Offen"}
	open_count = frappe.db.count("CAMT Bank Transaction", filters_open)

	filters_confirmed = {**filters, "status": "Bestätigt"}
	confirmed_count = frappe.db.count("CAMT Bank Transaction", filters_confirmed)

	filters_ignored = {**filters, "status": "Ignoriert"}
	ignored_count = frappe.db.count("CAMT Bank Transaction", filters_ignored)

	# Beträge
	filters_credit = {**filters, "credit_debit": "CRDT", "status": ["!=", "Ignoriert"]}
	total_credits = frappe.db.sql(
		"""SELECT COALESCE(SUM(amount), 0) FROM `tabCAMT Bank Transaction`
		WHERE credit_debit = 'CRDT' AND status != 'Ignoriert'
		{conditions}""".format(
			conditions=_build_conditions(filters)
		)
	)

	filters_debit = {**filters, "credit_debit": "DBIT", "status": ["!=", "Ignoriert"]}
	total_debits = frappe.db.sql(
		"""SELECT COALESCE(SUM(amount), 0) FROM `tabCAMT Bank Transaction`
		WHERE credit_debit = 'DBIT' AND status != 'Ignoriert'
		{conditions}""".format(
			conditions=_build_conditions(filters)
		)
	)

	return {
		"total": total,
		"open": open_count,
		"confirmed": confirmed_count,
		"ignored": ignored_count,
		"total_credits": total_credits[0][0] if total_credits else 0,
		"total_debits": total_debits[0][0] if total_debits else 0,
	}


def _build_conditions(filters):
	"""SQL-Bedingungen aus Filtern erstellen."""
	conditions = []
	if filters.get("camt_import"):
		conditions.append(f"AND camt_import = '{frappe.db.escape(filters['camt_import'])}'")
	if filters.get("bank_account"):
		conditions.append(f"AND bank_account = '{frappe.db.escape(filters['bank_account'])}'")
	return " ".join(conditions)


@frappe.whitelist()
def get_bank_transactions_page(
	start=0,
	page_length=20,
	status=None,
	camt_import=None,
	bank_account=None,
	credit_debit=None,
	from_date=None,
	to_date=None,
	search=None,
	hide_confirmed=False,
):
	"""Paginierte Transaktionsliste für die Page-Ansicht."""
	filters = {}

	if status:
		filters["status"] = status
	if camt_import:
		filters["camt_import"] = camt_import
	if bank_account:
		filters["bank_account"] = bank_account
	if credit_debit:
		filters["credit_debit"] = credit_debit
	if from_date:
		filters["booking_date"] = [">=", from_date]
	if to_date:
		if "booking_date" in filters:
			filters["booking_date"] = ["between", [from_date, to_date]]
		else:
			filters["booking_date"] = ["<=", to_date]

	if hide_confirmed and hide_confirmed != "false":
		filters["status"] = ["!=", "Bestätigt"]

	or_filters = None
	if search:
		or_filters = [
			["counterparty_name", "like", f"%{search}%"],
			["remittance_info", "like", f"%{search}%"],
			["additional_info", "like", f"%{search}%"],
			["counterparty_iban", "like", f"%{search}%"],
			["creditor_reference", "like", f"%{search}%"],
		]

	transactions = frappe.get_all(
		"CAMT Bank Transaction",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"camt_import",
			"status",
			"transaction_type",
			"booking_date",
			"value_date",
			"amount",
			"currency",
			"credit_debit",
			"signed_amount",
			"counterparty_name",
			"counterparty_iban",
			"remittance_info",
			"additional_info",
			"creditor_reference",
			"end_to_end_id",
			"confirmed_by",
			"confirmed_at",
			"bank_account",
			"match_status",
			"matched_invoice_type",
			"matched_invoice",
			"matched_party",
			"payment_entry",
			"journal_entry",
		],
		order_by="booking_date desc, name desc",
		start=cint(start),
		page_length=cint(page_length),
	)

	total_count = frappe.db.count("CAMT Bank Transaction", filters=filters)

	return {
		"transactions": transactions,
		"total_count": total_count,
	}


# ─────────────────────────────────────────────────────
# QRR / ESR Matching
# ─────────────────────────────────────────────────────

@frappe.whitelist()
def match_invoice_by_qrr(transaction_name):
	"""Versucht, eine Transaktion via QRR-Referenz einer Sales Invoice zuzuordnen.

	Sucht im Feld 'esr_reference_code' (swiss_accounting_software) nach
	der creditor_reference aus der CAMT-Transaktion.
	"""
	txn = frappe.get_doc("CAMT Bank Transaction", transaction_name)

	if not txn.creditor_reference:
		return {"status": "error", "message": _("Keine QRR-Referenz vorhanden.")}

	# Leerzeichen entfernen und normalisieren
	qrr = txn.creditor_reference.strip().replace(" ", "")

	# In Sales Invoice nach esr_reference_code suchen
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={
			"esr_reference_code": qrr,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
		},
		fields=["name", "customer", "customer_name", "outstanding_amount", "grand_total", "currency"],
		limit=5,
	)

	# Auch ohne führende Nullen suchen (manche Banken kürzen die Referenz)
	if not invoices:
		qrr_stripped = qrr.lstrip("0")
		invoices = frappe.get_all(
			"Sales Invoice",
			filters=[
				["esr_reference_code", "like", f"%{qrr_stripped}"],
				["docstatus", "=", 1],
				["outstanding_amount", ">", 0],
			],
			fields=["name", "customer", "customer_name", "outstanding_amount", "grand_total", "currency"],
			limit=5,
		)

	if not invoices:
		return {"status": "not_found", "message": _("Keine offene Sales Invoice mit dieser QRR-Referenz gefunden.")}

	if len(invoices) == 1:
		inv = invoices[0]
		txn.matched_invoice_type = "Sales Invoice"
		txn.matched_invoice = inv.name
		txn.matched_party_type = "Customer"
		txn.matched_party = inv.customer
		txn.match_status = "Zugeordnet"
		txn.match_method = "QRR-Referenz"
		txn.save(ignore_permissions=True)
		frappe.db.commit()
		return {
			"status": "matched",
			"invoice": inv.name,
			"customer": inv.customer_name,
			"outstanding": inv.outstanding_amount,
			"message": _("Zugeordnet zu {0} ({1})").format(inv.name, inv.customer_name),
		}

	# Mehrere Treffer – dem User die Wahl lassen
	return {
		"status": "multiple",
		"invoices": invoices,
		"message": _("{0} mögliche Rechnungen gefunden.").format(len(invoices)),
	}


@frappe.whitelist()
def match_all_by_qrr(camt_import=None):
	"""Auto-Matching aller offenen CRDT-Transaktionen via QRR-Referenz."""
	filters = {
		"credit_debit": "CRDT",
		"match_status": ["in", ["Offen", ""]],
		"creditor_reference": ["is", "set"],
	}
	if camt_import:
		filters["camt_import"] = camt_import

	txns = frappe.get_all(
		"CAMT Bank Transaction",
		filters=filters,
		pluck="name",
	)

	matched = 0
	not_found = 0

	for txn_name in txns:
		result = match_invoice_by_qrr(txn_name)
		if result.get("status") == "matched":
			matched += 1
		else:
			not_found += 1

	return {
		"matched": matched,
		"not_found": not_found,
		"total": len(txns),
		"message": _("{0} von {1} Transaktionen zugeordnet.").format(matched, len(txns)),
	}


@frappe.whitelist()
def assign_invoice(transaction_name, invoice_type, invoice_name):
	"""Manuelle Zuordnung einer Rechnung zu einer Transaktion."""
	txn = frappe.get_doc("CAMT Bank Transaction", transaction_name)
	inv = frappe.get_doc(invoice_type, invoice_name)

	if invoice_type == "Sales Invoice":
		txn.matched_party_type = "Customer"
		txn.matched_party = inv.customer
	elif invoice_type == "Purchase Invoice":
		txn.matched_party_type = "Supplier"
		txn.matched_party = inv.supplier

	txn.matched_invoice_type = invoice_type
	txn.matched_invoice = invoice_name
	txn.match_status = "Zugeordnet"
	txn.match_method = "Manuell"
	txn.save(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "ok", "message": _("Rechnung {0} zugeordnet.").format(invoice_name)}


@frappe.whitelist()
def unassign_invoice(transaction_name):
	"""Zuordnung einer Rechnung aufheben."""
	txn = frappe.get_doc("CAMT Bank Transaction", transaction_name)
	txn.matched_invoice_type = ""
	txn.matched_invoice = ""
	txn.matched_party_type = ""
	txn.matched_party = ""
	txn.match_status = "Offen"
	txn.match_method = ""
	txn.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok", "message": _("Zuordnung aufgehoben.")}


# ─────────────────────────────────────────────────────
# Payment Entry erstellen
# ─────────────────────────────────────────────────────

@frappe.whitelist()
def create_payment_entry(transaction_name):
	"""Erstellt einen Payment Entry aus einer zugeordneten CAMT-Transaktion.

	- CRDT + Sales Invoice → Payment Entry (Receive)
	- DBIT + Purchase Invoice → Payment Entry (Pay)
	"""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	txn = frappe.get_doc("CAMT Bank Transaction", transaction_name)

	if not txn.matched_invoice:
		frappe.throw(_("Keine Rechnung zugeordnet. Bitte zuerst eine Rechnung zuordnen."))

	if txn.payment_entry:
		frappe.throw(_("Es existiert bereits ein Payment Entry: {0}").format(txn.payment_entry))

	# Payment Entry via ERPNext-Helper erstellen
	pe = get_payment_entry(txn.matched_invoice_type, txn.matched_invoice)

	# Bankdaten überschreiben
	pe.posting_date = txn.booking_date
	pe.reference_no = txn.account_service_reference or txn.creditor_reference or txn.transaction_id or txn.name
	pe.reference_date = txn.booking_date
	pe.remarks = _("Erstellt aus CAMT-Transaktion {0}").format(txn.name)

	# Betrag setzen
	if pe.payment_type == "Receive":
		pe.paid_amount = float(txn.amount)
		pe.received_amount = float(txn.amount)
	else:
		pe.paid_amount = float(txn.amount)
		pe.received_amount = float(txn.amount)

	# Bankkonto setzen falls konfiguriert
	if txn.bank_account:
		bank_account_doc = frappe.get_doc("Bank Account", txn.bank_account)
		if bank_account_doc.account:
			if pe.payment_type == "Receive":
				pe.paid_to = bank_account_doc.account
			else:
				pe.paid_from = bank_account_doc.account

	# Allocated Amount in den Referenzen anpassen
	if pe.references and len(pe.references) > 0:
		pe.references[0].allocated_amount = float(txn.amount)

	pe.insert(ignore_permissions=True)

	# Verknüpfung speichern
	txn.payment_entry = pe.name
	txn.match_status = "Gebucht"
	txn.status = "Bestätigt"
	txn.confirmed_by = frappe.session.user
	txn.confirmed_at = now_datetime()
	txn.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "ok",
		"payment_entry": pe.name,
		"message": _("Payment Entry {0} erstellt (Entwurf).").format(pe.name),
	}


# ─────────────────────────────────────────────────────
# Journal Entry erstellen
# ─────────────────────────────────────────────────────

@frappe.whitelist()
def create_journal_entry(transaction_name, debit_account, credit_account, cost_center=None, remarks=None):
	"""Erstellt einen Journal Entry aus einer CAMT-Transaktion.

	Für Transaktionen ohne Rechnungsbezug (Bankgebühren, Löhne, etc.).
	Wird nur noch als Fallback genutzt – bevorzugt wird der Standarddialog.
	"""
	txn = frappe.get_doc("CAMT Bank Transaction", transaction_name)

	if txn.journal_entry:
		frappe.throw(_("Es existiert bereits ein Journal Entry: {0}").format(txn.journal_entry))

	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		frappe.throw(_("Bitte zuerst eine Standard-Firma konfigurieren."))

	amount = float(txn.amount)

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.posting_date = txn.booking_date
	je.company = company
	je.user_remark = remarks or _("Erstellt aus CAMT-Transaktion {0}: {1}").format(
		txn.name, txn.additional_info or txn.remittance_info or ""
	)
	je.cheque_no = txn.account_service_reference or txn.transaction_id or txn.name
	je.cheque_date = txn.booking_date
	je.camt_bank_transaction = txn.name

	je.append("accounts", {
		"account": debit_account,
		"debit_in_account_currency": amount,
		"cost_center": cost_center,
	})
	je.append("accounts", {
		"account": credit_account,
		"credit_in_account_currency": amount,
		"cost_center": cost_center,
	})

	je.insert(ignore_permissions=True)

	# Verknüpfung speichern
	txn.journal_entry = je.name
	txn.match_status = "Gebucht"
	txn.status = "Bestätigt"
	txn.confirmed_by = frappe.session.user
	txn.confirmed_at = now_datetime()
	txn.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "ok",
		"journal_entry": je.name,
		"message": _("Journal Entry {0} erstellt (Entwurf).").format(je.name),
	}


# ─────────────────────────────────────────────────────
# Hooks: Journal Entry ↔ CAMT Verknüpfung
# ─────────────────────────────────────────────────────

def link_journal_entry_to_camt(doc, method=None):
	"""Hook: after_insert auf Journal Entry.

	Wenn ein Journal Entry das Feld camt_bank_transaction gesetzt hat,
	wird die Verknüpfung auf der CAMT-Transaktion automatisch gesetzt.
	"""
	camt_txn_name = doc.get("camt_bank_transaction")
	if not camt_txn_name:
		return

	if not frappe.db.exists("CAMT Bank Transaction", camt_txn_name):
		return

	txn = frappe.get_doc("CAMT Bank Transaction", camt_txn_name)
	if txn.journal_entry:
		return  # Bereits verknüpft

	txn.journal_entry = doc.name
	txn.match_status = "Gebucht"
	txn.save(ignore_permissions=True)


def on_journal_entry_submit(doc, method=None):
	"""Hook: on_submit auf Journal Entry.

	Wenn ein verknüpfter Journal Entry gebucht wird,
	wird die CAMT-Transaktion automatisch bestätigt.
	"""
	camt_txn_name = doc.get("camt_bank_transaction")
	if not camt_txn_name:
		return

	if not frappe.db.exists("CAMT Bank Transaction", camt_txn_name):
		return

	txn = frappe.get_doc("CAMT Bank Transaction", camt_txn_name)
	if txn.status != "Bestätigt":
		txn.status = "Bestätigt"
		txn.confirmed_by = frappe.session.user
		txn.confirmed_at = now_datetime()
	txn.match_status = "Gebucht"
	txn.save(ignore_permissions=True)


def link_payment_entry_to_camt(doc, method=None):
	"""Hook: after_insert auf Payment Entry.

	Wenn ein Payment Entry das Feld camt_bank_transaction gesetzt hat,
	wird die Verknüpfung auf der CAMT-Transaktion automatisch gesetzt.
	"""
	camt_txn_name = doc.get("camt_bank_transaction")
	if not camt_txn_name:
		return

	if not frappe.db.exists("CAMT Bank Transaction", camt_txn_name):
		return

	txn = frappe.get_doc("CAMT Bank Transaction", camt_txn_name)
	if txn.payment_entry:
		return  # Bereits verknüpft

	txn.payment_entry = doc.name
	txn.match_status = "Gebucht"
	txn.save(ignore_permissions=True)


def on_payment_entry_submit(doc, method=None):
	"""Hook: on_submit auf Payment Entry.

	Wenn ein verknüpfter Payment Entry gebucht wird,
	wird die CAMT-Transaktion automatisch bestätigt.
	"""
	camt_txn_name = doc.get("camt_bank_transaction")
	if not camt_txn_name:
		return

	if not frappe.db.exists("CAMT Bank Transaction", camt_txn_name):
		return

	txn = frappe.get_doc("CAMT Bank Transaction", camt_txn_name)
	if txn.status != "Bestätigt":
		txn.status = "Bestätigt"
		txn.confirmed_by = frappe.session.user
		txn.confirmed_at = now_datetime()
	txn.match_status = "Gebucht"
	txn.save(ignore_permissions=True)


@frappe.whitelist()
def get_bank_accounts_with_transactions():
	"""Gibt alle Bankkonten zurück, die CAMT-Transaktionen haben.

	Für die Tab-Navigation auf der Übersichtsseite.
	"""
	accounts = frappe.db.sql("""
		SELECT DISTINCT
			cbt.bank_account,
			ba.account_name,
			ba.bank,
			ba.iban,
			ba.account as gl_account,
			COUNT(cbt.name) as txn_count,
			SUM(CASE WHEN cbt.status = 'Offen' THEN 1 ELSE 0 END) as open_count
		FROM `tabCAMT Bank Transaction` cbt
		LEFT JOIN `tabBank Account` ba ON ba.name = cbt.bank_account
		WHERE cbt.bank_account IS NOT NULL AND cbt.bank_account != ''
		GROUP BY cbt.bank_account
		ORDER BY ba.account_name
	""", as_dict=True)

	return accounts


@frappe.whitelist()
def get_accounts_for_journal(company=None):
	"""Kontenliste für Journal Entry Dialog laden."""
	if not company:
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")

	accounts = frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 0, "disabled": 0},
		fields=["name", "account_name", "account_type", "root_type"],
		order_by="name",
		limit=500,
	)
	return accounts
