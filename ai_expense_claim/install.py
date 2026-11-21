import frappe

# Names match Expense Claim Type autoname (field:expense_type).
DEFAULT_EXPENSE_CLAIM_TYPES = (
	("Food", "Expenses related to meals and food items"),
	("Travel", "Travel and transportation expenses"),
	("Accommodation", "Hotel and lodging expenses"),
	("Fuel", "Fuel and vehicle expenses"),
	("Communication", "Phone, internet, and communication expenses"),
	("Others", "Expenses that do not match a more specific type"),
)


def after_install():
	"""Seed expense claim types used when matching extracted receipts."""
	create_default_expense_claim_types()


def create_default_expense_claim_types():
	"""Create default Expense Claim Types that are not already on the site.

	Skips the step when ERPNext has not installed Expense Claim Type yet,
	so app installation itself is not blocked. Returns the names that were created.
	"""
	if not frappe.db.exists("DocType", "Expense Claim Type"):
		frappe.logger("ai_expense_claim").warning(
			"Skipped default expense claim types because Expense Claim Type is not installed"
		)
		return []

	has_description = frappe.get_meta("Expense Claim Type").has_field("description")
	created = []

	for expense_type, description in DEFAULT_EXPENSE_CLAIM_TYPES:
		if frappe.db.exists("Expense Claim Type", {"expense_type": expense_type}):
			continue

		doc = frappe.new_doc("Expense Claim Type")
		doc.expense_type = expense_type
		if has_description:
			doc.description = description

		try:
			doc.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			continue
		except Exception:
			frappe.log_error(
				title=f"AI Expense Claim: could not create Expense Claim Type {expense_type}",
				message=frappe.get_traceback(),
			)
			continue

		created.append(expense_type)

	if created:
		frappe.logger("ai_expense_claim").info(
			"Created expense claim types: {0}".format(", ".join(created))
		)

	return created
