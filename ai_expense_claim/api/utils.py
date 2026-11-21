import base64
import binascii
import os

import frappe
from frappe import _
from frappe.utils import flt

MAX_FILES = 10
MAX_FILE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
FALLBACK_EXPENSE_TYPES = ("others", "other", "miscellaneous")


def get_ai_expense_settings():
	"""Return processing settings without exposing the API key.

	Employees can process receipts. Only System Manager can open the settings form.
	"""
	if not frappe.db.exists("DocType", "AI Expense Settings"):
		frappe.throw(_("AI Expense Settings is not installed."))

	fields = (
		"openai_model",
		"max_token",
		"min_confidence_for_bills",
		"upload_ai_processed_bills_as_private_files",
		"merge_payment_proofs_with_bills",
		"duplicate_detection_amount_tolerance",
		"group_same_date_same_type_expenses",
	)
	settings = frappe._dict({field: frappe.db.get_single_value("AI Expense Settings", field) for field in fields})
	if not any(value not in (None, "") for value in settings.values()):
		frappe.throw(_("Open AI Expense Settings, add the OpenAI API key, and save it before processing receipts."))
	return settings


def decode_file(file_row):
	raw = file_row.get("data") or ""
	if "," in raw:
		raw = raw.split(",", 1)[1]
	return base64.b64decode(raw)


def prepare_upload(file_row):
	"""Validate one client upload and return bytes plus a safe file name."""
	if not isinstance(file_row, dict):
		frappe.throw(_("A receipt upload was incomplete. Choose the file again."))

	name = os.path.basename(str(file_row.get("name") or "receipt")).replace("\x00", "").strip() or "receipt"
	name = name[-140:]
	mime = str(file_row.get("type") or "").split(";", 1)[0].strip().lower()

	try:
		content = decode_file(file_row)
	except (binascii.Error, ValueError, TypeError):
		frappe.throw(_("Could not read {0}. Upload the file again.").format(name))

	if not content:
		frappe.throw(_("{0} is empty.").format(name))
	if len(content) > MAX_FILE_BYTES:
		frappe.throw(_("{0} is larger than 8 MB.").format(name))

	if mime in ALLOWED_IMAGE_TYPES:
		if not _matches_image(content, mime):
			frappe.throw(_("{0} is not a valid JPEG, PNG, or WEBP image.").format(name))
		data_url = file_row.get("data") or ""
		if not str(data_url).startswith("data:"):
			data_url = f"data:{mime};base64,{base64.b64encode(content).decode()}"
	elif mime == "application/pdf" or name.lower().endswith(".pdf"):
		mime = "application/pdf"
		data_url = ""
		if not content.startswith(b"%PDF"):
			frappe.throw(_("{0} is not a valid PDF.").format(name))
	else:
		frappe.throw(_("{0} is not supported. Use PDF, JPG, PNG, or WEBP.").format(name))

	return frappe._dict(name=name, mime=mime, content=content, data_url=data_url)


def match_expense_type(category, expense_types):
	"""Match a model category to a site Expense Claim Type.

	Unknown categories use Others when that type exists. They are left blank
	otherwise, so a receipt is not filed under an unrelated type.
	"""
	types = [exp_type for exp_type in (expense_types or []) if exp_type]
	if not types:
		return ""

	by_lower = {}
	for exp_type in types:
		by_lower.setdefault(exp_type.lower(), exp_type)

	cleaned = " ".join(str(category or "").split())
	if cleaned.lower() in by_lower:
		return by_lower[cleaned.lower()]

	if len(cleaned) >= 4:
		cleaned_lower = cleaned.lower()
		for exp_type in types:
			low = exp_type.lower()
			if len(low) >= 4 and (cleaned_lower in low or low in cleaned_lower):
				return exp_type

	for fallback in FALLBACK_EXPENSE_TYPES:
		if fallback in by_lower:
			return by_lower[fallback]
	return ""


def calculate_group_amount(items, tolerance=0):
	if not items:
		return 0

	payment_types = {"upi", "payment"}
	bills = []
	payments = []

	for item in items:
		doc_type = (item.get("document_type") or "receipt").lower()
		if doc_type in payment_types:
			payments.append(item)
		else:
			bills.append(item)

	total_amount = 0
	used_payments = set()

	for bill in bills:
		bill_amount = flt(bill.get("amount", 0))
		for idx, payment in enumerate(payments):
			if idx in used_payments:
				continue
			payment_amount = flt(payment.get("amount", 0))
			if abs(bill_amount - payment_amount) <= tolerance:
				used_payments.add(idx)
				break
		total_amount += bill_amount

	for idx, payment in enumerate(payments):
		if idx in used_payments:
			continue
		total_amount += flt(payment.get("amount", 0))

	return total_amount


def create_group(item):
	desc = (item.get("description") or "").strip()
	confidence = flt(item.get("confidence", 0))
	file_name = item.get("file_doc_name")

	return {
		"expense_type": item.get("expense_type") or "",
		"expense_date": item.get("expense_date") or "",
		"items": [item],
		"descriptions": [desc] if desc else [],
		"file_doc_names": [file_name] if file_name else [],
		"confidences": [confidence] if confidence else [],
		"best_confidence": confidence,
	}


def create_individual_groups(results):
	return [create_group(item) for item in results]


def merge_group_data(target, source):
	target["items"].extend(source["items"])
	target["descriptions"].extend([d for d in source["descriptions"] if d not in target["descriptions"]])
	target["file_doc_names"].extend([f for f in source["file_doc_names"] if f not in target["file_doc_names"]])
	target["confidences"].extend(source["confidences"])

	if source.get("best_confidence", 0) > target.get("best_confidence", 0):
		target["best_confidence"] = source["best_confidence"]
		if source.get("expense_date"):
			target["expense_date"] = source["expense_date"]
		if source.get("expense_type"):
			target["expense_type"] = source["expense_type"]

	target_type = (target.get("expense_type") or "others").lower()
	source_type = (source.get("expense_type") or "others").lower()
	if target_type == "others" and source_type != "others":
		target["expense_type"] = source["expense_type"]
		if source.get("expense_date"):
			target["expense_date"] = source["expense_date"]


def merge_payment_proof_groups(grouped_items, tolerance):
	payment_types = {"upi", "payment"}

	anchors = []
	orphans = []

	for group in grouped_items:
		expense_type = (group.get("expense_type") or "others").lower()
		doc_types = {(item.get("document_type") or "receipt").lower() for item in group["items"]}
		is_payment_only = doc_types.issubset(payment_types)
		is_others = expense_type == "others"

		if is_others and is_payment_only:
			orphans.append(group)
		else:
			anchors.append(group)

	unmatched_orphans = []
	for orphan in orphans:
		orphan_date = orphan.get("expense_date")
		orphan_amount = flt(orphan["items"][0].get("amount", 0) if orphan["items"] else 0)

		matched = False
		for anchor in anchors:
			anchor_date = anchor.get("expense_date")
			anchor_amount = flt(calculate_group_amount(anchor["items"], tolerance=0))
			if orphan_date != anchor_date:
				continue
			if abs(orphan_amount - anchor_amount) > tolerance:
				continue

			merge_group_data(anchor, orphan)
			matched = True
			break

		if not matched:
			unmatched_orphans.append(orphan)

	return anchors + unmatched_orphans


def consolidate_same_type_groups(grouped_items):
	consolidated_map = {}
	skipped = []

	for group in grouped_items:
		expense_date = group.get("expense_date") or ""
		expense_type = group.get("expense_type") or "Others"

		if not expense_date or (expense_type or "others").lower() == "others":
			skipped.append(group)
			continue

		key = (expense_date, expense_type)
		if key not in consolidated_map:
			consolidated_map[key] = group
		else:
			merge_group_data(consolidated_map[key], group)

	return list(consolidated_map.values()) + skipped


def _matches_image(content, mime):
	if mime == "image/jpeg":
		return content.startswith(b"\xff\xd8\xff")
	if mime == "image/png":
		return content.startswith(b"\x89PNG\r\n\x1a\n")
	if mime == "image/webp":
		return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
	return False
