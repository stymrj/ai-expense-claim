import io
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today
from frappe.utils.file_manager import save_file
from PIL import Image
from pypdf import PdfReader, PdfWriter

from ai_expense_claim.api.utils import (
	MAX_FILES,
	calculate_group_amount,
	consolidate_same_type_groups,
	create_individual_groups,
	get_ai_expense_settings,
	match_expense_type,
	merge_payment_proof_groups,
	prepare_upload,
)
from ai_expense_claim.integration.openai import extract_from_image, extract_from_pdf, get_openai_client

DOCUMENT_TYPES = {"bill", "receipt", "upi", "payment", "ticket"}
ALLOWED_MODELS = {"gpt-4o", "gpt-4o-mini"}


def ensure_can_process_expenses():
	if frappe.session.user == "Guest":
		frappe.throw(_("Log in to process receipts."), frappe.PermissionError)
	if frappe.has_permission("Expense Claim", "write") or frappe.has_permission("Expense Claim", "create"):
		return
	frappe.throw(_("You do not have permission to add expenses."), frappe.PermissionError)


@frappe.whitelist()
def process_bills(files, settings=None):
	"""Extract receipt fields. Client settings are ignored."""
	ensure_can_process_expenses()
	return _process_bills(frappe.parse_json(files), get_ai_expense_settings())


@frappe.whitelist()
def prepare_grouped_expenses(files):
	ensure_can_process_expenses()
	settings = get_ai_expense_settings()
	response = _process_bills(frappe.parse_json(files), settings)

	results = response.get("results", [])
	low_confidence_files = response.get("low_confidence_files", [])
	if not results:
		return {
			"groups": [],
			"low_confidence_files": low_confidence_files,
			"group_same_date_same_type_expenses": cint(settings.get("group_same_date_same_type_expenses")),
		}

	results.sort(key=lambda row: flt(row.get("confidence", 0)), reverse=True)

	tolerance = 0
	if cint(settings.get("merge_payment_proofs_with_bills")):
		tolerance = flt(settings.get("duplicate_detection_amount_tolerance"))

	grouped_items = create_individual_groups(results)
	if cint(settings.get("merge_payment_proofs_with_bills")):
		grouped_items = merge_payment_proof_groups(grouped_items, tolerance)
	if cint(settings.get("group_same_date_same_type_expenses")):
		grouped_items = consolidate_same_type_groups(grouped_items)

	return {
		"groups": build_final_groups(grouped_items, settings, tolerance),
		"low_confidence_files": low_confidence_files,
		"group_same_date_same_type_expenses": cint(settings.get("group_same_date_same_type_expenses")),
	}


@frappe.whitelist()
def link_files_to_claim(file_doc_names, docname):
	ensure_can_process_expenses()
	if not docname or not frappe.db.exists("Expense Claim", docname):
		frappe.throw(_("Save the Expense Claim before attaching receipts."))

	claim = frappe.get_doc("Expense Claim", docname)
	if claim.docstatus != 0:
		frappe.throw(_("Receipts can only be added to a draft Expense Claim."))
	if not claim.has_permission("write"):
		frappe.throw(_("You cannot update this Expense Claim."), frappe.PermissionError)

	names = frappe.parse_json(file_doc_names) or []
	if isinstance(names, str):
		names = [names]
	for name in names:
		if name:
			_attach_file_to_claim(name, claim.name)


@frappe.whitelist()
def discard_processed_files(file_doc_names):
	"""Delete unattached receipts the current user uploaded and then cancelled."""
	ensure_can_process_expenses()
	names = frappe.parse_json(file_doc_names) or []
	if isinstance(names, str):
		names = [names]
	for name in names:
		if isinstance(name, str) and name:
			_discard_file(name)


@frappe.whitelist()
def merge_files_for_group(file_doc_names, is_private=0):
	ensure_can_process_expenses()
	settings = get_ai_expense_settings()
	return _merge_files(file_doc_names, cint(settings.get("upload_ai_processed_bills_as_private_files")))


@frappe.whitelist()
def merge_attachments_by_url(url1, url2):
	ensure_can_process_expenses()
	name1 = frappe.get_value("File", {"file_url": url1}, "name") if url1 else None
	name2 = frappe.get_value("File", {"file_url": url2}, "name") if url2 else None
	names = [name for name in (name1, name2) if name]

	if not names:
		return url2 or url1
	if len(names) == 1:
		return url2 if name2 else url1

	settings = get_ai_expense_settings()
	return _merge_files(names, cint(settings.get("upload_ai_processed_bills_as_private_files")))


def link_claim_attachments(doc, method=None):
	"""Attach receipt files to the claim when a draft is saved."""
	if not doc or doc.docstatus != 0:
		return

	for row in doc.get("expenses") or []:
		url = row.get("custom_attachment")
		if not url:
			continue
		file_name = frappe.db.get_value("File", {"file_url": url}, "name")
		if not file_name:
			continue
		try:
			_attach_file_to_claim(file_name, doc.name)
		except Exception:
			frappe.log_error(title="AI Expense Claim file link", message=frappe.get_traceback())


def _process_bills(files, settings):
	if not isinstance(files, list) or not files:
		frappe.throw(_("No files provided."))
	if len(files) > MAX_FILES:
		frappe.throw(_("Process at most {0} receipts at a time.").format(MAX_FILES))

	prepared = [prepare_upload(row) for row in files]
	client = get_openai_client(settings)
	model = settings.get("openai_model") or "gpt-4o"
	if model not in ALLOWED_MODELS:
		model = "gpt-4o"
	token = cint(settings.get("max_token")) or 300
	token = min(max(token, 200), 4096)

	raw_minimum = settings.get("min_confidence_for_bills")
	minimum = 85 if raw_minimum in (None, "") else flt(raw_minimum)
	expense_types = frappe.get_all("Expense Claim Type", pluck="name", order_by="name asc")
	is_private = cint(settings.get("upload_ai_processed_bills_as_private_files"))

	results = []
	low_confidence_files = []
	errors = []

	workers = min(4, len(prepared))
	with ThreadPoolExecutor(max_workers=workers) as executor:
		futures = {
			executor.submit(_extract_receipt, client, model, token, item, expense_types): item for item in prepared
		}
		for future in as_completed(futures):
			item = futures[future]
			try:
				info = future.result() or {}
			except Exception:
				traceback = frappe.get_traceback()
				errors.append(traceback)
				frappe.log_error(title="AI Bill Extraction Error", message=traceback)
				low_confidence_files.append(
					{
						"file": item.name,
						"confidence": 0,
						"reason": _public_failure_reason(traceback),
					}
				)
				continue

			if not isinstance(info, dict):
				info = {}

			confidence = _confidence(info.get("confidence"))
			reason = " ".join(str(info.get("reason") or "").split())[:240]
			if confidence < minimum:
				low_confidence_files.append(
					{
						"file": item.name,
						"confidence": confidence,
						"reason": reason or "Document unreadable or not a valid bill/receipt",
					}
				)
				continue

			try:
				file_doc = save_file(
					fname=_stored_file_name(item),
					content=item.content,
					dt=None,
					dn=None,
					folder="Home",
					is_private=is_private,
				)
			except Exception:
				traceback = frappe.get_traceback()
				errors.append(traceback)
				frappe.log_error(title="AI Expense Claim file save", message=traceback)
				low_confidence_files.append(
					{
						"file": item.name,
						"confidence": 0,
						"reason": "Could not store this file",
					}
				)
				continue

			document_type = str(info.get("document_type") or "receipt").lower()
			if document_type not in DOCUMENT_TYPES:
				document_type = "receipt"

			amount = flt(info.get("amount"), 2)
			results.append(
				{
					"expense_date": _expense_date(info.get("date")),
					"expense_type": match_expense_type(info.get("category"), expense_types),
					"amount": amount if amount > 0 else 0,
					"description": str(info.get("description") or "")[:140],
					"file_doc_name": file_doc.name,
					"confidence": confidence,
					"document_type": document_type,
				}
			)

	results.sort(key=lambda row: (row["expense_date"], row["expense_type"]))
	_raise_if_extraction_failed(errors, results, len(prepared))
	return {"results": results, "low_confidence_files": low_confidence_files}


def _extract_receipt(client, model, token, item, expense_types):
	"""Run in a worker thread. Must not touch Frappe or the database."""
	if item.mime.startswith("image/"):
		return extract_from_image(client, model, token, item.data_url, expense_types)
	return extract_from_pdf(client, model, token, item.content, expense_types)


def build_final_groups(grouped_items, settings, tolerance):
	groups = []
	is_private = cint(settings.get("upload_ai_processed_bills_as_private_files"))

	for group in grouped_items:
		confidences = group["confidences"]
		avg_confidence = sum(confidences) / len(confidences) if confidences else 95.0
		attachment_url = ""
		attachment_name = ""

		if group["file_doc_names"]:
			try:
				attachment_url = _merge_files(group["file_doc_names"], is_private) or ""
				if attachment_url:
					attachment_name = frappe.db.get_value("File", {"file_url": attachment_url}, "name") or ""
			except Exception:
				frappe.log_error(title="AI Expense Claim file merge", message=frappe.get_traceback())

		groups.append(
			{
				"expense_type": group["expense_type"],
				"expense_date": group["expense_date"],
				"avg_confidence": round(avg_confidence, 1),
				"amount": flt(calculate_group_amount(group["items"], tolerance), 2),
				"description": "; ".join(group["descriptions"])[:140],
				"attachment_url": attachment_url,
				"attachment_name": attachment_name,
				"file_doc_names": group["file_doc_names"],
			}
		)

	groups.sort(key=lambda row: (row["expense_date"] or "9999-12-31", row["expense_type"] or ""))
	return groups


def _merge_files(file_doc_names, is_private):
	if isinstance(file_doc_names, str):
		file_doc_names = frappe.parse_json(file_doc_names)
	if not file_doc_names:
		return None
	if len(file_doc_names) == 1:
		file_doc = _file_for_merge(file_doc_names[0])
		return file_doc.file_url

	writer = PdfWriter()
	for doc_name in file_doc_names:
		file_doc = _file_for_merge(doc_name)
		content = file_doc.get_content()
		ext = os.path.splitext(file_doc.file_name or "")[1].lower()
		if ext == ".pdf":
			reader = PdfReader(io.BytesIO(content))
			for page in reader.pages:
				writer.add_page(page)
			continue

		img = Image.open(io.BytesIO(content))
		if img.mode not in ("RGB", "L"):
			img = img.convert("RGB")
		img_pdf = io.BytesIO()
		img.save(img_pdf, format="PDF")
		img_pdf.seek(0)
		reader = PdfReader(img_pdf)
		for page in reader.pages:
			writer.add_page(page)

	if not writer.pages:
		return None

	output = io.BytesIO()
	writer.write(output)
	merged = save_file(
		fname="merged_receipts.pdf",
		content=output.getvalue(),
		dt=None,
		dn=None,
		folder="Home",
		is_private=cint(is_private),
	)
	return merged.file_url


def _file_for_merge(name):
	file_doc = frappe.get_doc("File", name)
	roles = set(frappe.get_roles())
	if file_doc.owner != frappe.session.user and "System Manager" not in roles:
		frappe.throw(_("You can only combine receipts you uploaded."), frappe.PermissionError)
	if file_doc.attached_to_doctype and file_doc.attached_to_doctype != "Expense Claim":
		frappe.throw(_("That file is already used on another document."), frappe.PermissionError)
	if file_doc.attached_to_name and not frappe.has_permission("Expense Claim", "write", file_doc.attached_to_name):
		frappe.throw(_("You cannot change attachments on this Expense Claim."), frappe.PermissionError)
	return file_doc


def _attach_file_to_claim(file_name, claim_name):
	current = frappe.db.get_value(
		"File",
		file_name,
		["owner", "attached_to_doctype", "attached_to_name"],
		as_dict=True,
	)
	if not current:
		return
	if current.attached_to_doctype or current.attached_to_name:
		if current.attached_to_doctype == "Expense Claim" and current.attached_to_name == claim_name:
			return
		return
	if current.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
		return

	frappe.db.set_value(
		"File",
		file_name,
		{"attached_to_doctype": "Expense Claim", "attached_to_name": claim_name},
		update_modified=False,
	)


def _discard_file(name):
	if not frappe.db.exists("File", name):
		return
	current = frappe.db.get_value("File", name, ["owner", "attached_to_name", "file_url"], as_dict=True)
	if not current or current.attached_to_name:
		return
	if current.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
		return
	if current.file_url and frappe.db.exists("Expense Claim Detail", {"custom_attachment": current.file_url}):
		return
	frappe.delete_doc("File", name, ignore_permissions=True)


def _stored_file_name(item):
	fallback = ".pdf" if item.mime == "application/pdf" else ".jpg"
	base = item.name
	if "." not in os.path.basename(base):
		base = f"{base}{fallback}"
	return base[-140:]


def _expense_date(value):
	if not value:
		return today()
	try:
		return getdate(value).isoformat()
	except Exception:
		return today()


def _confidence(value):
	if value is None or value == "":
		return 0
	if isinstance(value, str):
		value = value.strip().rstrip("%")
	return flt(value)


def _raise_if_extraction_failed(errors, results, prepared_count):
	if results or not errors or len(errors) < prepared_count:
		return
	blob = "\n".join(errors).lower()
	if any(token in blob for token in ("invalid_api_key", "incorrect api key")):
		frappe.throw(_("The OpenAI API key was rejected. Update it in AI Expense Settings."))
	if any(token in blob for token in ("poppler", "pdfinfo", "unable to get page count")):
		frappe.throw(_("Scanned PDFs need Poppler installed on the server. Text PDFs can still be processed."))
	frappe.throw(_("Could not read these receipts. Check AI Expense Settings, then try a clearer image or PDF."))


def _public_failure_reason(traceback_text):
	blob = (traceback_text or "").lower()
	if "invalid_api_key" in blob or "incorrect api key" in blob:
		return "OpenAI rejected the API key"
	if any(token in blob for token in ("poppler", "pdfinfo", "unable to get page count")):
		return "Scanned PDF support needs Poppler on the server"
	return "Could not read this file"
