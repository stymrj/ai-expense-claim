# Copyright (c) 2026, Manav Mandli and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from ai_expense_claim.api.utils import calculate_group_amount, match_expense_type


class TestExpenseUtils(FrappeTestCase):
	def test_exact_match_ignores_case(self):
		self.assertEqual(match_expense_type("food", ["Food", "Travel"]), "Food")

	def test_unknown_category_uses_others(self):
		self.assertEqual(match_expense_type("gadgets", ["Food", "Others"]), "Others")

	def test_unknown_category_without_others_stays_blank(self):
		self.assertEqual(match_expense_type("gadgets", ["Food", "Travel"]), "")

	def test_matching_payment_is_not_added_twice(self):
		items = [
			{"document_type": "bill", "amount": 100},
			{"document_type": "upi", "amount": 100},
		]
		self.assertEqual(calculate_group_amount(items, tolerance=1), 100)

	def test_unmatched_payment_is_kept(self):
		items = [
			{"document_type": "bill", "amount": 100},
			{"document_type": "upi", "amount": 40},
		]
		self.assertEqual(calculate_group_amount(items, tolerance=1), 140)
