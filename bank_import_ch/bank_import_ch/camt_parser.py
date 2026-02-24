"""
CAMT.053 Parser für Schweizer Banken.

Unterstützt die gängigen Versionen:
- camt.053.001.02
- camt.053.001.04
- camt.053.001.06
- camt.053.001.08
- camt.053.001.11

Parst die XML-Dateien und extrahiert alle relevanten Transaktionsdaten.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, date
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional


# Bekannte Namespaces für camt.053
CAMT_NAMESPACES = {
	"camt.053.001.02": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02",
	"camt.053.001.04": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.04",
	"camt.053.001.06": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.06",
	"camt.053.001.08": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08",
	"camt.053.001.11": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.11",
}


@dataclass
class CamtTransaction:
	"""Eine einzelne Banktransaktion aus einer CAMT.053-Datei."""

	# Identifikation
	entry_reference: str = ""
	account_service_reference: str = ""
	payment_info_id: str = ""
	instruction_id: str = ""
	end_to_end_id: str = ""

	# Beträge
	amount: Decimal = Decimal("0")
	currency: str = "CHF"
	credit_debit: str = ""  # "CRDT" oder "DBIT"

	# Daten
	booking_date: Optional[date] = None
	value_date: Optional[date] = None

	# Gegenpartei
	counterparty_name: str = ""
	counterparty_iban: str = ""
	counterparty_bic: str = ""
	counterparty_address: str = ""

	# Kontoinhaber
	account_iban: str = ""
	account_owner: str = ""

	# Beschreibung / Mitteilung
	remittance_info: str = ""
	additional_info: str = ""
	proprietary_purpose: str = ""
	domain_code: str = ""
	family_code: str = ""
	sub_family_code: str = ""

	# Status
	status: str = ""  # "BOOK", "PDNG", etc.
	reversal_indicator: bool = False

	# Referenzen
	mandate_id: str = ""
	creditor_reference: str = ""

	@property
	def is_credit(self) -> bool:
		return self.credit_debit == "CRDT"

	@property
	def is_debit(self) -> bool:
		return self.credit_debit == "DBIT"

	@property
	def signed_amount(self) -> Decimal:
		"""Betrag mit Vorzeichen: positiv für Gutschriften, negativ für Belastungen."""
		if self.is_debit:
			return -self.amount
		return self.amount

	@property
	def transaction_type(self) -> str:
		"""Menschenlesbarer Transaktionstyp."""
		if self.is_credit:
			return "Zahlungseingang"
		return "Zahlungsausgang"

	@property
	def description(self) -> str:
		"""Zusammengesetzte Beschreibung der Transaktion."""
		parts = []
		if self.remittance_info:
			parts.append(self.remittance_info)
		if self.additional_info:
			parts.append(self.additional_info)
		if not parts and self.proprietary_purpose:
			parts.append(self.proprietary_purpose)
		return " | ".join(parts) if parts else "Keine Beschreibung"


@dataclass
class CamtStatement:
	"""Ein Kontoauszug (Statement) aus einer CAMT.053-Datei."""

	statement_id: str = ""
	electronic_seq_number: str = ""
	creation_date: Optional[datetime] = None
	from_date: Optional[date] = None
	to_date: Optional[date] = None
	account_iban: str = ""
	account_owner: str = ""
	account_currency: str = "CHF"
	opening_balance: Decimal = Decimal("0")
	closing_balance: Decimal = Decimal("0")
	transactions: list = field(default_factory=list)


@dataclass
class CamtFile:
	"""Eine vollständige CAMT.053-Datei."""

	message_id: str = ""
	creation_date: Optional[datetime] = None
	camt_version: str = ""
	statements: list = field(default_factory=list)

	@property
	def all_transactions(self) -> list:
		"""Alle Transaktionen aus allen Statements."""
		txns = []
		for stmt in self.statements:
			txns.extend(stmt.transactions)
		return txns


def _find_text(element, path, ns, default=""):
	"""Hilfsfunktion: Text eines XML-Elements finden."""
	el = element.find(path, ns)
	if el is not None and el.text:
		return el.text.strip()
	return default


def _parse_date(date_str: str) -> Optional[date]:
	"""Datum-String parsen (verschiedene Formate)."""
	if not date_str:
		return None

	for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
				"%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
		try:
			dt = datetime.strptime(date_str.replace("+00:00", "+0000").replace("+01:00", "+0100").replace("+02:00", "+0200"), fmt)
			return dt.date() if isinstance(dt, datetime) else dt
		except ValueError:
			continue

	# Fallback: nur die ersten 10 Zeichen (YYYY-MM-DD)
	try:
		return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
	except (ValueError, IndexError):
		return None


def _parse_datetime(dt_str: str) -> Optional[datetime]:
	"""Datetime-String parsen."""
	if not dt_str:
		return None

	for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
				"%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
		try:
			return datetime.strptime(dt_str.replace("+00:00", "+0000").replace("+01:00", "+0100").replace("+02:00", "+0200"), fmt)
		except ValueError:
			continue

	try:
		return datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
	except (ValueError, IndexError):
		return None


def _detect_namespace(root) -> tuple:
	"""Namespace aus dem Root-Element erkennen."""
	tag = root.tag
	if "}" in tag:
		ns_uri = tag.split("}")[0].lstrip("{")
		# Version aus Namespace extrahieren
		for version, uri in CAMT_NAMESPACES.items():
			if uri == ns_uri:
				return {"ns": ns_uri}, version

		# Unbekannter Namespace, aber trotzdem versuchen
		return {"ns": ns_uri}, "unknown"

	# Kein Namespace
	return {}, "unknown"


def _parse_entry(entry_el, ns_dict, account_iban="", account_owner="") -> list:
	"""Eine Ntry (Entry) parsen. Kann mehrere Transaktionen enthalten."""
	ns = ns_dict
	prefix = "ns:" if ns else ""
	transactions = []

	# Entry-Level Daten
	entry_ref = _find_text(entry_el, f"{prefix}NtryRef", ns)
	acct_svc_ref = _find_text(entry_el, f"{prefix}AcctSvcrRef", ns)

	# Betrag auf Entry-Level
	amt_el = entry_el.find(f"{prefix}Amt", ns)
	entry_amount = Decimal("0")
	entry_currency = "CHF"
	if amt_el is not None:
		try:
			entry_amount = Decimal(amt_el.text.strip())
		except Exception:
			pass
		entry_currency = amt_el.get("Ccy", "CHF")

	credit_debit = _find_text(entry_el, f"{prefix}CdtDbtInd", ns)
	reversal = _find_text(entry_el, f"{prefix}RvslInd", ns) == "true"
	status = _find_text(entry_el, f"{prefix}Sts", ns)

	# Neuere Versionen haben Sts/Cd statt direkt Sts
	if not status:
		status = _find_text(entry_el, f"{prefix}Sts/{prefix}Cd", ns)

	# Buchungsdatum
	booking_date_str = _find_text(entry_el, f"{prefix}BookgDt/{prefix}Dt", ns)
	if not booking_date_str:
		booking_date_str = _find_text(entry_el, f"{prefix}BookgDt/{prefix}DtTm", ns)
	booking_date = _parse_date(booking_date_str)

	# Valutadatum
	value_date_str = _find_text(entry_el, f"{prefix}ValDt/{prefix}Dt", ns)
	if not value_date_str:
		value_date_str = _find_text(entry_el, f"{prefix}ValDt/{prefix}DtTm", ns)
	value_date = _parse_date(value_date_str)

	# Zusätzliche Infos auf Entry-Level
	add_info = _find_text(entry_el, f"{prefix}AddtlNtryInf", ns)

	# Bank Transaction Code
	domain_code = _find_text(entry_el, f"{prefix}BkTxCd/{prefix}Domn/{prefix}Cd", ns)
	family_code = _find_text(entry_el, f"{prefix}BkTxCd/{prefix}Domn/{prefix}Fmly/{prefix}Cd", ns)
	sub_family_code = _find_text(entry_el, f"{prefix}BkTxCd/{prefix}Domn/{prefix}Fmly/{prefix}SubFmlyCd", ns)
	proprietary = _find_text(entry_el, f"{prefix}BkTxCd/{prefix}Prtry/{prefix}Cd", ns)

	# Entry Details (NtryDtls) – kann mehrere TxDtls enthalten
	ntry_dtls_list = entry_el.findall(f"{prefix}NtryDtls", ns)

	has_tx_details = False

	for ntry_dtls in ntry_dtls_list:
		tx_dtls_list = ntry_dtls.findall(f"{prefix}TxDtls", ns)

		for tx_dtls in tx_dtls_list:
			has_tx_details = True
			txn = CamtTransaction(
				entry_reference=entry_ref,
				account_service_reference=acct_svc_ref,
				credit_debit=credit_debit,
				reversal_indicator=reversal,
				status=status,
				booking_date=booking_date,
				value_date=value_date,
				account_iban=account_iban,
				account_owner=account_owner,
				additional_info=add_info,
				domain_code=domain_code,
				family_code=family_code,
				sub_family_code=sub_family_code,
				proprietary_purpose=proprietary,
			)

			# Referenzen
			txn.payment_info_id = _find_text(tx_dtls, f"{prefix}Refs/{prefix}PmtInfId", ns)
			txn.instruction_id = _find_text(tx_dtls, f"{prefix}Refs/{prefix}InstrId", ns)
			txn.end_to_end_id = _find_text(tx_dtls, f"{prefix}Refs/{prefix}EndToEndId", ns)
			txn.mandate_id = _find_text(tx_dtls, f"{prefix}Refs/{prefix}MndtId", ns)
			txn.creditor_reference = _find_text(tx_dtls, f"{prefix}Refs/{prefix}CdtrRef", ns)

			# Betrag auf TxDtls-Level (überschreibt Entry-Level)
			tx_amt_el = tx_dtls.find(f"{prefix}Amt", ns)
			if tx_amt_el is not None:
				try:
					txn.amount = Decimal(tx_amt_el.text.strip())
				except Exception:
					txn.amount = entry_amount
				txn.currency = tx_amt_el.get("Ccy", entry_currency)
			else:
				txn.amount = entry_amount
				txn.currency = entry_currency

			# CdtDbtInd auf TxDtls-Level (kann Entry-Level überschreiben)
			tx_cdi = _find_text(tx_dtls, f"{prefix}CdtDbtInd", ns)
			if tx_cdi:
				txn.credit_debit = tx_cdi

			# Gegenpartei – abhängig von Richtung
			if txn.is_credit:
				# Bei Gutschrift: Debtor = Gegenpartei (wer zahlt)
				party_path = f"{prefix}RltdPties/{prefix}Dbtr"
				party_acct_path = f"{prefix}RltdPties/{prefix}DbtrAcct"
			else:
				# Bei Belastung: Creditor = Gegenpartei (wem wird gezahlt)
				party_path = f"{prefix}RltdPties/{prefix}Cdtr"
				party_acct_path = f"{prefix}RltdPties/{prefix}CdtrAcct"

			txn.counterparty_name = _find_text(tx_dtls, f"{party_path}/{prefix}Nm", ns)
			if not txn.counterparty_name:
				# v08+: Name ist unter Pty verschachtelt: <Dbtr><Pty><Nm>
				txn.counterparty_name = _find_text(tx_dtls, f"{party_path}/{prefix}Pty/{prefix}Nm", ns)

			# Adresse – zuerst direkt, dann unter Pty
			addr_base = f"{party_path}/{prefix}PstlAdr"
			# Prüfe ob Adresse unter Pty liegt (v08+)
			addr_check = tx_dtls.find(f"{party_path}/{prefix}Pty/{prefix}PstlAdr", ns)
			if addr_check is not None:
				addr_base = f"{party_path}/{prefix}Pty/{prefix}PstlAdr"

			addr_lines = tx_dtls.findall(f"{addr_base}/{prefix}AdrLine", ns)
			if addr_lines:
				txn.counterparty_address = ", ".join(
					line.text.strip() for line in addr_lines if line.text
				)
			else:
				street = _find_text(tx_dtls, f"{addr_base}/{prefix}StrtNm", ns)
				bldg = _find_text(tx_dtls, f"{addr_base}/{prefix}BldgNb", ns)
				pcd = _find_text(tx_dtls, f"{addr_base}/{prefix}PstCd", ns)
				town = _find_text(tx_dtls, f"{addr_base}/{prefix}TwnNm", ns)
				parts = []
				if street:
					parts.append(f"{street} {bldg}".strip())
				if pcd or town:
					parts.append(f"{pcd} {town}".strip())
				txn.counterparty_address = ", ".join(parts)

			# IBAN der Gegenpartei – direkt oder unter Pty
			txn.counterparty_iban = _find_text(
				tx_dtls, f"{party_acct_path}/{prefix}Id/{prefix}IBAN", ns
			)

			# BIC
			if txn.is_credit:
				bic_path = f"{prefix}RltdAgts/{prefix}DbtrAgt/{prefix}FinInstnId/{prefix}BIC"
				bic_path2 = f"{prefix}RltdAgts/{prefix}DbtrAgt/{prefix}FinInstnId/{prefix}BICFI"
			else:
				bic_path = f"{prefix}RltdAgts/{prefix}CdtrAgt/{prefix}FinInstnId/{prefix}BIC"
				bic_path2 = f"{prefix}RltdAgts/{prefix}CdtrAgt/{prefix}FinInstnId/{prefix}BICFI"

			txn.counterparty_bic = _find_text(tx_dtls, bic_path, ns)
			if not txn.counterparty_bic:
				txn.counterparty_bic = _find_text(tx_dtls, bic_path2, ns)
			# v08+: BIC unter FinInstnId/BICFI
			if not txn.counterparty_bic:
				if txn.is_credit:
					txn.counterparty_bic = _find_text(
						tx_dtls, f"{prefix}RltdAgts/{prefix}DbtrAgt/{prefix}FinInstnId/{prefix}BICFI", ns
					)
				else:
					txn.counterparty_bic = _find_text(
						tx_dtls, f"{prefix}RltdAgts/{prefix}CdtrAgt/{prefix}FinInstnId/{prefix}BICFI", ns
					)

			# Verwendungszweck / Remittance Information
			# Unstrukturiert
			ustrd = _find_text(tx_dtls, f"{prefix}RmtInf/{prefix}Ustrd", ns)
			# Strukturiert – Creditor Reference
			strd_ref = _find_text(
				tx_dtls,
				f"{prefix}RmtInf/{prefix}Strd/{prefix}CdtrRefInf/{prefix}Ref",
				ns,
			)
			if not strd_ref:
				strd_ref = _find_text(
					tx_dtls,
					f"{prefix}RmtInf/{prefix}Strd/{prefix}CdtrRefInf/{prefix}CdtrRef",
					ns,
				)

			if ustrd:
				txn.remittance_info = ustrd
			elif strd_ref:
				txn.remittance_info = strd_ref

			if strd_ref and not txn.creditor_reference:
				txn.creditor_reference = strd_ref

			# Zusätzliche Infos auf TxDtls-Level
			tx_add_info = _find_text(tx_dtls, f"{prefix}AddtlTxInf", ns)
			if tx_add_info:
				txn.additional_info = tx_add_info

			transactions.append(txn)

	# Falls keine TxDtls gefunden wurden, Entry-Level Transaktion erstellen
	if not has_tx_details:
		txn = CamtTransaction(
			entry_reference=entry_ref,
			account_service_reference=acct_svc_ref,
			amount=entry_amount,
			currency=entry_currency,
			credit_debit=credit_debit,
			reversal_indicator=reversal,
			status=status,
			booking_date=booking_date,
			value_date=value_date,
			account_iban=account_iban,
			account_owner=account_owner,
			additional_info=add_info,
			domain_code=domain_code,
			family_code=family_code,
			sub_family_code=sub_family_code,
			proprietary_purpose=proprietary,
		)
		transactions.append(txn)

	return transactions


def parse_camt053(xml_content: str) -> CamtFile:
	"""
	CAMT.053 XML-Inhalt parsen.

	Args:
		xml_content: Der XML-Inhalt als String.

	Returns:
		CamtFile-Objekt mit allen geparsten Daten.
	"""
	root = ET.fromstring(xml_content)
	ns_dict, version = _detect_namespace(root)

	# Namespace-Prefix für XPath
	if ns_dict:
		ns = {"ns": ns_dict["ns"]}
		prefix = "ns:"
	else:
		ns = {}
		prefix = ""

	camt_file = CamtFile(camt_version=version)

	# BkToCstmrStmt finden
	bk_stmt = root.find(f"{prefix}BkToCstmrStmt", ns)
	if bk_stmt is None:
		# Versuche direkt unter Root
		bk_stmt = root
		# Nochmal suchen ohne Namespace
		for child in root:
			local_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
			if local_name == "BkToCstmrStmt":
				bk_stmt = child
				break

	# Group Header
	grp_hdr = bk_stmt.find(f"{prefix}GrpHdr", ns)
	if grp_hdr is not None:
		camt_file.message_id = _find_text(grp_hdr, f"{prefix}MsgId", ns)
		camt_file.creation_date = _parse_datetime(
			_find_text(grp_hdr, f"{prefix}CreDtTm", ns)
		)

	# Statements
	for stmt_el in bk_stmt.findall(f"{prefix}Stmt", ns):
		stmt = CamtStatement()
		stmt.statement_id = _find_text(stmt_el, f"{prefix}Id", ns)
		stmt.electronic_seq_number = _find_text(stmt_el, f"{prefix}ElctrncSeqNb", ns)
		stmt.creation_date = _parse_datetime(
			_find_text(stmt_el, f"{prefix}CreDtTm", ns)
		)

		# Zeitraum
		stmt.from_date = _parse_date(
			_find_text(stmt_el, f"{prefix}FrToDt/{prefix}FrDtTm", ns)
		)
		stmt.to_date = _parse_date(
			_find_text(stmt_el, f"{prefix}FrToDt/{prefix}ToDtTm", ns)
		)

		# Konto
		stmt.account_iban = _find_text(
			stmt_el, f"{prefix}Acct/{prefix}Id/{prefix}IBAN", ns
		)
		stmt.account_owner = _find_text(
			stmt_el, f"{prefix}Acct/{prefix}Ownr/{prefix}Nm", ns
		)
		stmt.account_currency = _find_text(
			stmt_el, f"{prefix}Acct/{prefix}Ccy", ns, "CHF"
		)

		# Saldi
		for bal_el in stmt_el.findall(f"{prefix}Bal", ns):
			bal_type = _find_text(bal_el, f"{prefix}Tp/{prefix}CdOrPrtry/{prefix}Cd", ns)
			bal_amt_el = bal_el.find(f"{prefix}Amt", ns)
			if bal_amt_el is not None:
				try:
					bal_amount = Decimal(bal_amt_el.text.strip())
				except Exception:
					bal_amount = Decimal("0")

				bal_cdi = _find_text(bal_el, f"{prefix}CdtDbtInd", ns)
				if bal_cdi == "DBIT":
					bal_amount = -bal_amount

				if bal_type in ("OPBD", "PRCD"):
					stmt.opening_balance = bal_amount
				elif bal_type in ("CLBD", "CLAV"):
					stmt.closing_balance = bal_amount

		# Entries (Transaktionen)
		for entry_el in stmt_el.findall(f"{prefix}Ntry", ns):
			txns = _parse_entry(
				entry_el, ns, stmt.account_iban, stmt.account_owner
			)
			stmt.transactions.extend(txns)

		camt_file.statements.append(stmt)

	return camt_file
