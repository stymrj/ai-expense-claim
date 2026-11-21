# Copyright (c) 2026, Manav Mandli and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class AIExpenseSettings(Document):
	def validate(self):
		confidence = cint(self.min_confidence_for_bills)
		if confidence < 0 or confidence > 100:
			frappe.throw(_("Min confidence for bills must be between 0 and 100."))

		tokens = cint(self.max_token)
		if tokens < 200 or tokens > 4096:
			frappe.throw(_("Max Token must be between 200 and 4096."))
