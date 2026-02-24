app_name = "bank_import_ch"
app_title = "Bank Import CH"
app_publisher = "Your Company"
app_description = "CAMT.053 Bank Transaction Import für ERPNext (Swiss Edition)"
app_email = "your@email.com"
app_license = "MIT"

# App-Icon und Farbe
app_icon = "octicon octicon-credit-card"
app_color = "#e74c3c"

# Module
add_to_apps_screen = [
	{
		"name": "bank_import_ch",
		"logo": "/assets/bank_import_ch/images/logo.png",
		"title": "Bank Import CH",
		"route": "/app/bank-transactions-ch",
		"has_permission": "bank_import_ch.permissions.has_permission",
	}
]

# Fixtures
# fixtures = []

# DocType Registrierung
# doc_events = {}

# Website
website_route_rules = [
	{
		"from_route": "/bank-transactions-ch/<path:app_path>",
		"to_route": "bank-transactions-ch",
	},
]

# App-spezifische CSS/JS
# app_include_css = "/assets/bank_import_ch/css/bank_import_ch.css"
# app_include_js = "/assets/bank_import_ch/js/bank_import_ch.js"
