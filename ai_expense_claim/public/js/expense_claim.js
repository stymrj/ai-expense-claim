frappe.ui.form.on("Expense Claim", {
	refresh(frm) {
		frm.toggle_display("custom_upload_process_aibased_bills", frm.doc.docstatus === 0);
	},
	custom_upload_process_aibased_bills(frm) {
		if (frm.doc.docstatus !== 0) {
			frappe.msgprint(__("Receipts can only be added to a draft Expense Claim."));
			return;
		}
		if (window.show_ai_bill_processor) {
			window.show_ai_bill_processor(frm);
		} else {
			frappe.msgprint({
				title: __("Error"),
				message: __("AI Bill Processor is not loaded. Refresh the page after building the app."),
				indicator: "red",
			});
		}
	},
});
