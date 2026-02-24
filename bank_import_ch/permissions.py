import frappe


def has_permission():
	"""Check if user has permission to access Bank Import CH."""
	return frappe.has_permission("CAMT Import", ptype="read")
