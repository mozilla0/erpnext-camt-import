"""CAMT Import Controller.

Handles the import of CAMT.053 files and creation of CAMT Bank Transaction records.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, cint, flt
from decimal import Decimal

from bank_import_ch.bank_import_ch.camt_parser import parse_camt053


class CAMTImport(Document):
	def before_save(self):
		if self.camt_file and not self.message_id:
			self.process_camt_file()

	def process_camt_file(self):
		"""CAMT.053-Datei lesen und verarbeiten."""
		file_doc = frappe.get_doc("File", {"file_url": self.camt_file})
		file_content = file_doc.get_content()

		if isinstance(file_content, bytes):
			file_content = file_content.decode("utf-8")

		camt_file = parse_camt053(file_content)

		# Metadaten setzen
		self.message_id = camt_file.message_id
		self.camt_version = camt_file.camt_version
		self.import_date = now_datetime()
		self.imported_by = frappe.session.user
		self.file_name = (self.camt_file or "").split("/")[-1]

		if camt_file.statements:
			stmt = camt_file.statements[0]  # Erster Statement
			self.account_iban = stmt.account_iban
			self.account_owner = stmt.account_owner
			self.account_currency = stmt.account_currency
			self.statement_from_date = stmt.from_date
			self.statement_to_date = stmt.to_date
			self.opening_balance = float(stmt.opening_balance)
			self.closing_balance = float(stmt.closing_balance)

		# Transaktionen zählen
		all_txns = camt_file.all_transactions
		self.total_transactions = len(all_txns)
		self.total_credits = sum(
			float(t.amount) for t in all_txns if t.is_credit
		)
		self.total_debits = sum(
			float(t.amount) for t in all_txns if t.is_debit
		)
		self.pending_transactions = len(all_txns)
		self.confirmed_transactions = 0
		self.status = "Importiert"

	def after_insert(self):
		"""Nach dem Speichern: Transaktionsdatensätze erstellen."""
		if self.camt_file and self.status == "Importiert":
			self.create_transactions()

	def create_transactions(self):
		"""Einzelne CAMT Bank Transaction Datensätze erstellen.

		Nutzt die transaction_id (IBAN + AcctSvcRef) für globale Duplikatprüfung
		über alle Imports hinweg. Gibt Feedback über importierte/übersprungene Einträge.
		"""
		file_doc = frappe.get_doc("File", {"file_url": self.camt_file})
		file_content = file_doc.get_content()

		if isinstance(file_content, bytes):
			file_content = file_content.decode("utf-8")

		camt_file = parse_camt053(file_content)

		created = 0
		skipped_duplicate = 0
		skipped_no_id = 0

		for txn in camt_file.all_transactions:
			txn_id = txn.transaction_id

			# Globale Duplikatprüfung über alle Imports hinweg
			existing = frappe.db.exists(
				"CAMT Bank Transaction",
				{"transaction_id": txn_id},
			)

			if existing:
				skipped_duplicate += 1
				continue

			doc = frappe.new_doc("CAMT Bank Transaction")
			doc.camt_import = self.name
			doc.transaction_id = txn_id
			doc.entry_reference = txn.entry_reference
			doc.account_service_reference = txn.account_service_reference
			doc.end_to_end_id = txn.end_to_end_id
			doc.payment_info_id = txn.payment_info_id
			doc.amount = float(txn.amount)
			doc.currency = txn.currency
			doc.credit_debit = txn.credit_debit
			doc.signed_amount = float(txn.signed_amount)
			doc.booking_date = txn.booking_date
			doc.value_date = txn.value_date
			doc.counterparty_name = txn.counterparty_name
			doc.counterparty_iban = txn.counterparty_iban
			doc.counterparty_bic = txn.counterparty_bic
			doc.counterparty_address = txn.counterparty_address
			doc.account_iban = txn.account_iban
			doc.remittance_info = txn.remittance_info
			doc.additional_info = txn.additional_info
			doc.transaction_type = txn.transaction_type
			doc.creditor_reference = txn.creditor_reference
			doc.domain_code = txn.domain_code
			doc.family_code = txn.family_code
			doc.sub_family_code = txn.sub_family_code
			doc.bank_account = self.bank_account
			doc.status = "Offen"
			doc.insert(ignore_permissions=True)
			created += 1

		frappe.db.commit()

		# Zusammenfassung aktualisieren
		self.reload()
		self.update_summary()

		# Benutzer-Feedback
		msg_parts = []
		if created:
			msg_parts.append(f"<b>{created}</b> Transaktionen importiert")
		if skipped_duplicate:
			msg_parts.append(f"<b>{skipped_duplicate}</b> Duplikate übersprungen")

		if msg_parts:
			indicator = "green" if not skipped_duplicate else "orange"
			frappe.msgprint(
				"<br>".join(msg_parts),
				title="Import abgeschlossen",
				indicator=indicator,
			)
		elif not created and not skipped_duplicate:
			frappe.msgprint(
				"Keine Transaktionen in der Datei gefunden.",
				title="Import",
				indicator="red",
			)

		return {"created": created, "skipped": skipped_duplicate}

	def update_summary(self):
		"""Zusammenfassung aktualisieren."""
		confirmed = frappe.db.count(
			"CAMT Bank Transaction",
			{"camt_import": self.name, "status": "Bestätigt"},
		)
		total = frappe.db.count(
			"CAMT Bank Transaction",
			{"camt_import": self.name},
		)
		self.confirmed_transactions = cint(confirmed)
		self.pending_transactions = cint(total) - cint(confirmed)

		if confirmed == total and total > 0:
			self.status = "Vollständig bestätigt"
		elif confirmed > 0:
			self.status = "Teilweise bestätigt"
		else:
			self.status = "Importiert"

		self.save(ignore_permissions=True)


@frappe.whitelist()
def import_camt_file(camt_import_name):
	"""Manueller Re-Import einer CAMT-Datei."""
	doc = frappe.get_doc("CAMT Import", camt_import_name)
	doc.create_transactions()
	return {"message": f"{doc.total_transactions} Transaktionen importiert."}
