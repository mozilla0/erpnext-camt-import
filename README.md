# Bank Import CH

CAMT.053 Banktransaktions-Import für ERPNext v16 – optimiert für Schweizer Banken (Raiffeisen, PostFinance, UBS, ZKB u.a.)

---

<img width="2552" height="1088" alt="Bildschirmfoto_20260701_135622" src="https://github.com/user-attachments/assets/de2064b2-c0fa-476c-a81d-a760d1b9b731" />
<img width="2552" height="617" alt="Bildschirmfoto_20260701_135554" src="https://github.com/user-attachments/assets/c6718a92-0f33-4e3b-a4d2-7b106d885f6e" />


## 🇨🇭 Deutsch

### Funktionen

#### CAMT.053 Import
- Unterstützt alle gängigen Versionen: camt.053.001.02 bis .11 (automatische Erkennung)
- Reiner Python-Parser – keine externen Abhängigkeiten (nur stdlib `xml.etree`)
- Parst Gegenpartei-Details, IBAN, BIC, Adressen, QRR-Referenzen, Verwendungszweck
- Duplikaterkennung via eindeutiger Transaktions-ID (IBAN + AcctSvcRef)
- Feedback beim Import: Anzahl importierter vs. übersprungener Transaktionen

#### Transaktionsverwaltung
- Eigene Übersichtsseite unter `/app/bank-transactions-ch` mit Filtern, Suche und Massenaktionen
- Filter nach Status, Art (Eingang/Ausgang), Datum, Freitextsuche
- Einzel- und Massenbestätigung mit «Bestätigte ausblenden»-Toggle
- Detailansicht pro Transaktion mit allen CAMT-Feldern

#### Rechnungszuordnung
- **Auto-Matching** via QRR/ESR-Referenz gegen Sales Invoices (sucht im Feld `esr_reference_code` von [swiss_accounting_software](https://github.com/onfuseag/swiss_accounting_software))
- **Massen-Matching** vom CAMT Import Formular – ordnet alle offenen Gutschriften auf einmal zu
- **Manuelle Zuordnung** von Sales Invoices (Zahlungseingänge) und Purchase Invoices (Zahlungsausgänge)
- Zuordnungsstatus: Offen → Zugeordnet → Gebucht

#### Buchhaltungsintegration
- **Payment Entry**: Öffnet das vorausgefüllte ERPNext Standard-Formular aus zugeordneten Transaktionen
- **Journal Entry**: Öffnet das vorausgefüllte ERPNext Standard-Formular (nutze «From Template» für wiederkehrende Buchungen wie Löhne, Gebühren etc.)
- Automatische Verknüpfung: Beim Speichern eines PE/JE wird die CAMT-Transaktion automatisch verlinkt
- Automatische Bestätigung: Beim Buchen (Submit) eines PE/JE wird die CAMT-Transaktion als «Bestätigt» markiert

### Voraussetzungen

- ERPNext v16
- Frappe Framework v16
- Optional: [swiss_accounting_software](https://github.com/onfuseag/swiss_accounting_software) (für QRR Auto-Matching via `esr_reference_code`)

### Installation

#### Frappe Cloud

1. Diese App in ein GitHub-Repository pushen
2. Im Frappe Cloud Dashboard: Benches → Bench Group → Apps → Add App → Repo und Branch auswählen
3. Nach dem Deploy: Sites → Site → Apps → Install App → `bank_import_ch` auswählen

#### Lokal / Self-Hosted

```bash
bench get-app https://github.com/your-org/bank-import-ch.git
bench --site <sitename> install-app bank_import_ch
bench --site <sitename> migrate
```

### Anwendung

#### 1. CAMT.053-Datei importieren

**CAMT Import** öffnen (Suchleiste oder `/app/camt-import`) → Neu → XML-Datei hochladen → Speichern. Die Datei wird automatisch geparst und einzelne Transaktionsdatensätze erstellt.

#### 2. Transaktionen prüfen

`/app/bank-transactions-ch` für die Übersichtsseite öffnen, oder nach **CAMT Bank Transaction** in der Suchleiste suchen.

#### 3. Rechnungen zuordnen

**Automatisch (QRR):** Im CAMT Import Formular → *Aktionen → QRR Auto-Matching* – ordnet alle Zahlungseingänge mit QRR-Referenz auf einmal zu.

**Manuell:** Auf einer einzelnen Transaktion → *Zuordnung → Sales Invoice zuordnen* (oder Purchase Invoice für Zahlungsausgänge) → Rechnung auswählen.

#### 4. Buchungen erstellen

**Payment Entry:** Nach der Rechnungszuordnung → *Buchen → Payment Entry erstellen*. Öffnet das ERPNext Standard-Formular vorausgefüllt mit Buchungsdatum, Betrag, Referenz und verknüpfter Rechnung. Prüfen und buchen.

**Journal Entry:** Für Transaktionen ohne Rechnungsbezug (Löhne, Bankgebühren etc.) → *Buchen → Journal Entry erstellen*. Öffnet das Standard-Formular, wo über «From Template» eine Vorlage gewählt, Konten angepasst und direkt gebucht werden kann.

### Unterstützte Banken

Getestet mit Raiffeisen (camt.053.001.08). Kompatibel mit allen Schweizer Banken, die Standard-CAMT.053-Dateien liefern, u.a. PostFinance, UBS, Credit Suisse, ZKB, BCGE.

---

## 🇬🇧 English

### Features

#### CAMT.053 Import
- Supports all common versions: camt.053.001.02 through .11 (auto-detection)
- Pure Python parser – no external dependencies (stdlib `xml.etree` only)
- Parses counterparty details, IBAN, BIC, addresses, QRR references, remittance info
- Duplicate detection via unique transaction ID (IBAN + AcctSvcRef)
- Feedback on import: count of imported vs. skipped transactions

#### Transaction Management
- Custom page at `/app/bank-transactions-ch` with filtering, search and bulk actions
- Filter by status, type (credit/debit), date range, free text search
- Individual and bulk confirm/ignore with "hide confirmed" toggle
- Detail view per transaction with all CAMT fields

#### Invoice Matching
- **Auto-matching** via QRR/ESR reference against Sales Invoices (searches `esr_reference_code` field from [swiss_accounting_software](https://github.com/onfuseag/swiss_accounting_software))
- **Bulk matching** from CAMT Import form – matches all open credit transactions at once
- **Manual assignment** of Sales Invoices (for incoming payments) and Purchase Invoices (for outgoing payments)
- Match status tracking: Offen → Zugeordnet → Gebucht

#### Accounting Integration
- **Payment Entry**: opens pre-filled standard ERPNext Payment Entry form from matched transactions
- **Journal Entry**: opens pre-filled standard ERPNext Journal Entry form (use "From Template" for recurring bookings like salaries, fees, etc.)
- Auto-linking: saving a PE/JE automatically links it back to the CAMT transaction
- Auto-confirm: submitting a PE/JE automatically marks the CAMT transaction as confirmed

### Requirements

- ERPNext v16
- Frappe Framework v16
- Optional: [swiss_accounting_software](https://github.com/onfuseag/swiss_accounting_software) (for QRR auto-matching via `esr_reference_code`)

### Installation

#### Frappe Cloud

1. Push this app to a GitHub repository
2. In Frappe Cloud: Benches → your Bench Group → Apps → Add App → select the repo and branch
3. After deploy: Sites → your Site → Apps → Install App → select `bank_import_ch`

#### Local / Self-hosted

```bash
bench get-app https://github.com/your-org/bank-import-ch.git
bench --site <sitename> install-app bank_import_ch
bench --site <sitename> migrate
```

### Usage

#### 1. Import CAMT.053 file

Navigate to **CAMT Import** (search bar or `/app/camt-import`) → New → upload your XML file → Save. The file is parsed automatically and individual transaction records are created.

#### 2. Review transactions

Open `/app/bank-transactions-ch` for the overview page, or search for **CAMT Bank Transaction** for the standard list view.

#### 3. Match invoices

**Automatic (QRR):** On the CAMT Import form, click *Actions → QRR Auto-Matching* to match all incoming payments with QRR references at once.

**Manual:** On a single transaction, click *Zuordnung → Sales Invoice zuordnen* (or Purchase Invoice for outgoing payments) and select the invoice.

#### 4. Create accounting entries

**Payment Entry:** After matching an invoice, click *Buchen → Payment Entry erstellen*. This opens the standard ERPNext Payment Entry form pre-filled with booking date, amount, reference and the linked invoice. Review and submit.

**Journal Entry:** For transactions without an invoice (salaries, bank fees, etc.), click *Buchen → Journal Entry erstellen*. This opens the standard Journal Entry form where you can select a template via "From Template", adjust accounts and submit directly.

### Supported Banks

Tested with Raiffeisen (camt.053.001.08). Compatible with any Swiss bank that produces standard CAMT.053 files, including PostFinance, UBS, Credit Suisse, ZKB, BCGE, and others.

---

## DocTypes

| DocType | Beschreibung / Description |
|---------|---------------------------|
| **CAMT Import** | Upload und Metadaten einer CAMT.053-Datei / Upload and metadata for a CAMT.053 XML file |
| **CAMT Bank Transaction** | Einzeltransaktion mit Details und Zuordnungs-/Buchungsstatus / Individual transaction with full details and matching/booking status |

## Custom Fields (via Fixtures)

| DocType | Feld / Field | Zweck / Purpose |
|---------|-------------|-----------------|
| Payment Entry | `camt_bank_transaction` | Verknüpfung zur CAMT-Transaktion / Link back to CAMT transaction |
| Journal Entry | `camt_bank_transaction` | Verknüpfung zur CAMT-Transaktion / Link back to CAMT transaction |

## Lizenz / License

MIT
