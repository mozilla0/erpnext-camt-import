"""CAMT Bank Transaction Controller."""

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CAMTBankTransaction(Document):
	def on_update(self):
		"""Bei Statusänderung: Import-Zusammenfassung aktualisieren."""
		if self.has_value_changed("status"):
			if self.status == "Bestätigt" and not self.confirmed_at:
				self.db_set("confirmed_by", frappe.session.user)
				self.db_set("confirmed_at", now_datetime())
			elif self.status == "Offen":
				self.db_set("confirmed_by", "")
				self.db_set("confirmed_at", None)

			# Import-Zusammenfassung aktualisieren
			if self.camt_import:
				try:
					import_doc = frappe.get_doc("CAMT Import", self.camt_import)
					import_doc.update_summary()
				except Exception:
					pass
