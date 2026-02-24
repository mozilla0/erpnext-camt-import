// List View Einstellungen für CAMT Import

frappe.listview_settings["CAMT Import"] = {
	add_fields: ["status", "total_transactions", "confirmed_transactions", "pending_transactions"],

	get_indicator(doc) {
		if (doc.status === "Vollständig bestätigt") {
			return [__("Vollständig bestätigt"), "green", "status,=,Vollständig bestätigt"];
		}
		if (doc.status === "Teilweise bestätigt") {
			return [__("Teilweise bestätigt"), "orange", "status,=,Teilweise bestätigt"];
		}
		if (doc.status === "Importiert") {
			return [__("Importiert"), "blue", "status,=,Importiert"];
		}
		return [__("Entwurf"), "grey", "status,=,Entwurf"];
	},
};
