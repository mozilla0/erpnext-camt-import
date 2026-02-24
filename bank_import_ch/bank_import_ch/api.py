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
