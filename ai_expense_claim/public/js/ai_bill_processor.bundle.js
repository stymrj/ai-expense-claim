window.show_ai_bill_processor = function(frm) {
	if (frm.doc.docstatus !== 0) {
		frappe.msgprint(__("Receipts can only be added to a draft Expense Claim."));
		return;
	}

	let files = [];
	let processing = false;
	let sortable = null;

	const dialog = new frappe.ui.Dialog({
		title: __("AI Bill Processor"),
		size: "large",
		fields: [
			{
				fieldname: "upload_html",
				fieldtype: "HTML"
			}
		],
		primary_action_label: __("Process with AI"),
		primary_action: process_files,
		secondary_action_label: __("Cancel"),
		secondary_action: () => dialog.hide()
	});
	

	dialog.$wrapper.addClass("ai-bill-processor-dialog");
	dialog.show();
	
	render_upload_ui();
	update_button_state();

	function render_upload_ui() {
		const wrapper = dialog.fields_dict.upload_html.$wrapper;
		
		wrapper.html(`
			<input type="file" id="ai_file_input" multiple accept="image/*,.pdf" style="display:none">
			<div class="ai-dropzone" id="ai_dropzone">
				<div class="ai-drop-icon">${frappe.utils.icon("upload", "xl")}</div>
				<p class="ai-drop-label">${__("Click or drop files here")}</p>
				<p class="ai-drop-hint">${__("PDF, JPG, PNG, or WEBP. Up to 10 files, 8 MB each.")}</p>
			</div>
			<div id="ai_file_list_container"></div>
		`);

		const dropzone = wrapper.find("#ai_dropzone");
		const file_input = wrapper.find("#ai_file_input");

		dropzone.attr({
			role: "button",
			tabindex: "0",
			"aria-controls": "ai_file_input",
			"aria-label": __("Choose receipts or drop files here")
		});
		file_input.attr("aria-label", __("Select receipt files"));

		dropzone.on("click", (e) => {
			e.preventDefault();
			file_input[0].click();
		});

		dropzone.on("keydown", (e) => {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				file_input[0].click();
			}
		});

		file_input.on("change", (e) => {
			add_files(Array.from(e.target.files));
			e.target.value = "";
		});

		dropzone.on("dragover", (e) => {
			e.preventDefault();
			e.stopPropagation();
			dropzone.addClass("dragover");
		});

		dropzone.on("dragleave", (e) => {
			e.preventDefault();
			e.stopPropagation();
			dropzone.removeClass("dragover");
		});

		dropzone.on("drop", (e) => {
			e.preventDefault();
			e.stopPropagation();
			dropzone.removeClass("dragover");
			add_files(Array.from(e.originalEvent.dataTransfer.files));
		});
		
		inject_styles();
	}

	function inject_styles() {
		if (document.getElementById("ai-upload-styles")) return;
		
		const style = document.createElement("style");
		style.id = "ai-upload-styles";
		style.textContent = `
			.ai-bill-processor-dialog .modal-body {
				max-height: 70vh;
				overflow-y: auto;
				-webkit-overflow-scrolling: touch;
			}
			.ai-dropzone {
				border: 2px dashed var(--border-color);
				border-radius: var(--border-radius-lg);
				padding: 48px 20px;
				text-align: center;
				cursor: pointer;
				transition: all 0.3s;
				background: var(--bg-light-gray);
				margin-bottom: 16px;
			}
			.ai-dropzone:hover {
				border-color: var(--primary);
				background: var(--blue-50, #eff6ff);
			}
			.ai-dropzone.dragover {
				border-color: var(--primary);
				background: var(--blue-100, #dbeafe);
				transform: scale(1.01);
			}
			.ai-drop-icon {
				font-size: 48px;
				color: var(--text-muted);
				margin-bottom: 12px;
			}
			.ai-drop-label {
				font-size: 15px;
				font-weight: 500;
				margin: 0 0 6px;
				color: var(--text-color);
			}
			.ai-drop-hint {
				font-size: 13px;
				color: var(--text-muted);
				margin: 0;
			}
			.ai-file-list {
				display: flex;
				flex-direction: column;
				gap: 8px;
				margin-top: 16px;
			}
			.ai-file-item {
				display: flex;
				align-items: center;
				gap: 12px;
				padding: 10px 12px;
				border: 1px solid var(--border-color);
				border-radius: var(--border-radius);
				background: var(--card-bg);
				transition: all 0.2s;
			}
			.ai-file-item:hover {
				background: var(--bg-light-gray);
			}
			.ai-drag-handle {
				cursor: grab;
				color: var(--text-muted);
				flex-shrink: 0;
			}
			.ai-drag-handle:active {
				cursor: grabbing;
			}                           
			.ai-file-thumb {
				width: 48px;
				height: 48px;
				border-radius: var(--border-radius-sm);
				overflow: hidden;
				flex-shrink: 0;
				background: var(--bg-light-gray);
				display: flex;
				align-items: center;
				justify-content: center;
			}
			.ai-file-thumb img {
				width: 100%;
				height: 100%;
				object-fit: cover;
			}
			.ai-file-info {
				flex: 1;
				min-width: 0;
			}
			.ai-file-name {
				font-size: 13px;
				font-weight: 500;
				margin-bottom: 2px;
				overflow: hidden;
				text-overflow: ellipsis;
				white-space: nowrap;
			}
			.ai-file-size {
				font-size: 12px;
				color: var(--text-muted);
			}
			.ai-file-actions {
				display: flex;
				gap: 6px;
				flex-shrink: 0;
			}
			.ai-list-header {
				display: flex;
				align-items: center;
				justify-content: space-between;
				margin: 16px 0 8px;
				font-size: 12px;
				color: var(--text-muted);
			}
			@media (max-width: 767px) {
				.ai-bill-processor-dialog .modal-dialog {
					width: calc(100% - 1rem);
					max-width: none;
					margin: 0.5rem auto;
				}
				.ai-bill-processor-dialog .modal-body {
					max-height: calc(100vh - 9rem);
					max-height: calc(100dvh - 9rem);
					padding: 1rem;
				}
				.ai-bill-processor-dialog .ai-dropzone {
					padding: 24px 12px;
					touch-action: manipulation;
				}
				.ai-bill-processor-dialog .ai-file-item {
					gap: 8px;
					padding: 8px;
				}
				.ai-bill-processor-dialog .ai-drag-handle {
					display: none;
				}
				.ai-bill-processor-dialog .ai-file-thumb {
					width: 40px;
					height: 40px;
				}
				.ai-bill-processor-dialog .ai-file-actions .btn,
				.ai-bill-processor-dialog .modal-footer .btn {
					min-width: 44px;
					min-height: 44px;
				}
				.ai-bill-processor-dialog .grid-body {
					overflow-x: auto;
					-webkit-overflow-scrolling: touch;
				}
			}
		`;
		document.head.appendChild(style);
	}

	function add_files(new_files) {
		const allowed = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
		const max_files = 10;
		const max_bytes = 8 * 1024 * 1024;
		let reported_limit = false;

		new_files.forEach(file => {
			if (files.length >= max_files) {
				if (!reported_limit) {
					reported_limit = true;
					frappe.show_alert({
						message: __("You can process up to {0} receipts at a time.", [max_files]),
						indicator: "orange"
					});
				}
				return;
			}

			if (file.size > max_bytes) {
				frappe.show_alert({
					message: __('"{0}" is larger than 8 MB.', [file.name]),
					indicator: "orange"
				});
				return;
			}

			if (!allowed.includes(file.type)) {
				frappe.show_alert({
					message: __('"{0}" is not supported. Use PDF or image files.', [file.name]),
					indicator: "orange"
				});
				return;
			}

			if (files.find(f => f.name === file.name && f.size === file.size)) {
				frappe.show_alert({
					message: __('"{0}" is already in the list.', [file.name]),
					indicator: "orange"
				});
				return;
			}

			if (file.type.startsWith("image/")) {
				const reader = new FileReader();
				reader.onload = (e) => {
					file.preview = e.target.result;
					render_file_list();
				};
				reader.readAsDataURL(file);
			}

			files.push(file);
		});

		render_file_list();
		update_button_state();
	}

	function render_file_list() {
		const wrapper = dialog.fields_dict.upload_html.$wrapper;
		const container = wrapper.find("#ai_file_list_container");

		if (!files.length) {
			container.html("");
			return;
		}

		let html = `
			<div class="ai-list-header">
				<span>${__("Files to process")}</span>
				<span class="badge badge-pill badge-primary">${files.length}</span>
			</div>
			<div class="ai-file-list" id="ai_sortable_list">
		`;

		files.forEach((file, idx) => {
			const size = format_file_size(file.size);
			const thumb = file.preview
				? `<img src="${file.preview}" alt="${frappe.utils.escape_html(file.name)}">`
				: `<div style="color: var(--text-muted);">${frappe.utils.icon("file", "md")}</div>`;
			
			html += `
				<div class="ai-file-item" data-idx="${idx}">
					<div class="ai-drag-handle">${frappe.utils.icon("drag", "sm")}</div>
					<div class="ai-file-thumb">${thumb}</div>
					<div class="ai-file-info">
						<div class="ai-file-name" title="${frappe.utils.escape_html(file.name)}">${frappe.utils.escape_html(file.name)}</div>
						<div class="ai-file-size">${size}</div>
					</div>
					<div class="ai-file-actions">
						<button class="btn btn-xs btn-default ai-remove-btn" data-idx="${idx}" title="${__("Remove")}">
							${frappe.utils.icon("delete", "sm")}
						</button>
					</div>
				</div>
			`;
		});

		html += `</div>`;
		container.html(html);

		container.find(".ai-remove-btn").on("click", function() {
			const idx = $(this).data("idx");
			files.splice(idx, 1);
			render_file_list();
			update_button_state();
		});

		init_sortable();
	}

	function init_sortable() {
		if (sortable) {
			sortable.destroy();
			sortable = null;
		}

		const list_el = dialog.fields_dict.upload_html.$wrapper.find("#ai_sortable_list")[0];
		if (window.Sortable && list_el && files.length > 1) {
			sortable = new window.Sortable(list_el, {
				animation: 150,
				handle: ".ai-drag-handle",
				onEnd(evt) {
					const moved = files.splice(evt.oldIndex, 1)[0];
					files.splice(evt.newIndex, 0, moved);
					setTimeout(render_file_list, 0);
				}
			});
		}
	}

	function format_file_size(bytes) {
		if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
		if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
		return bytes + " B";
	}

	function update_button_state() {
		dialog.get_primary_btn().prop("disabled", files.length === 0 || processing);
	}

	function process_files() {
		if (processing || !files.length) return;

		processing = true;
		dialog.hide();

		Promise.all(files.map(file_to_base64))
			.then(file_data => {
				return frappe.call({
					method: "ai_expense_claim.api.expense.prepare_grouped_expenses",
					args: { files: JSON.stringify(file_data) },
					freeze: true,
					freeze_message: __("Processing Your Bills...")
				});
			})
			.then(r => {
				const response = r.message || {};
				const groups = response.groups || [];
				const low_confidence_files = response.low_confidence_files || [];
				
				if (!groups.length && !low_confidence_files.length) {
					frappe.throw(__("No data could be extracted from the files."));
				}
				
				if (low_confidence_files.length > 0) {
					const warnings = low_confidence_files.map(f =>
						`<li><strong>${frappe.utils.escape_html(f.file || "")}</strong>: ${frappe.utils.escape_html(f.reason || "")} (${frappe.utils.escape_html(String(f.confidence ?? ""))}%)</li>`
					).join("");
					frappe.msgprint({
						title: __("Some Files Skipped"),
						message: `
							<p>${__("The following files were skipped because the read was not confident enough:")}</p>
							<ul>${warnings}</ul>
						`,
						indicator: "orange"
					});
					
					if (groups.length === 0) {
						dialog.show();
						return;
					}
				}
				
				show_results_dialog(frm, groups, response.group_same_date_same_type_expenses);
			})
			.catch(err => {
				dialog.show();
				frappe.msgprint({
					title: __("Error"),
					message: err.message || __("Failed to process bills"),
					indicator: "red"
				});
			})
			.finally(() => {
				processing = false;
			});
	}

	function file_to_base64(file) {
		return new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = (e) => resolve({
				name: file.name,
				data: e.target.result,
				type: file.type
			});
			reader.onerror = () => reject(new Error(__("Could not read {0}", [file.name])));
			reader.readAsDataURL(file);
		});
	}
};

async function show_results_dialog(frm, groups, group_same_type) {
	let applied = false;
	let form_updated = false;

	function names_from(rows) {
		const names = [];
		(rows || []).forEach((row) => {
			(row.file_doc_names || row._file_doc_names || []).forEach((name) => name && names.push(name));
			const attachment = row.attachment_name || row._attachment_name;
			if (attachment) names.push(attachment);
		});
		return [...new Set(names)];
	}

	function discard_files(names) {
		const unique = [...new Set((names || []).filter(Boolean))];
		if (!unique.length) return;
		frappe.call({
			method: "ai_expense_claim.api.expense.discard_processed_files",
			args: { file_doc_names: JSON.stringify(unique) },
		});
	}

	const review = new frappe.ui.Dialog({
		title: __("Review Extracted Expenses"),
		size: "extra-large",
		fields: [
			{
				fieldname: "expenses",
				fieldtype: "Table",
				label: __("Expenses"),
				options: "Expense Claim Detail",
				cannot_add_rows: true,
				cannot_delete_rows: true,
				in_place_edit: true,
				fields: [
					{ fieldname: "expense_date", fieldtype: "Date", label: __("Date"), in_list_view: 1, reqd: 1, columns: 1 },
					{ fieldname: "expense_type", fieldtype: "Link", options: "Expense Claim Type", label: __("Type"), in_list_view: 1, reqd: 1, columns: 2 },
					{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), in_list_view: 1, columns: 1 },
					{ fieldname: "description", fieldtype: "Small Text", label: __("Description"), in_list_view: 1, columns: 3 },
					{ fieldname: "custom_attachment", fieldtype: "Attach", label: __("Attachment"), in_list_view: 1, read_only: 1, columns: 2 },
				],
			}
		],
		primary_action_label: __("Add to Expense Claim"),
		primary_action: async function() {
			const selected = grid.get_selected_children();

			if (!selected.length) {
				frappe.show_alert({ message: __("Select at least one expense to add."), indicator: "orange" });
				return;
			}

			if (selected.some((row) => !row.expense_date || !row.expense_type || !(parseFloat(row.amount) > 0))) {
				frappe.show_alert({
					message: __("Each selected row needs a date, an expense type, and an amount."),
					indicator: "orange"
				});
				return;
			}

			const apply_btn = review.get_primary_btn();
			apply_btn.prop("disabled", true).text(__("Adding..."));

			try {
				for (const row of selected) {
					const existing = group_same_type
						? (frm.doc.expenses || []).find(
							(entry) => entry.expense_date === row.expense_date && entry.expense_type === row.expense_type
						)
						: null;

					if (existing) {
						existing.amount = parseFloat(existing.amount || 0) + parseFloat(row.amount || 0);
						if (row.description) {
							existing.description = [existing.description, row.description]
								.filter(Boolean)
								.join("; ")
								.slice(0, 500);
						}
						if (row.custom_attachment) {
							if (existing.custom_attachment && existing.custom_attachment !== row.custom_attachment) {
								const merged = await frappe.call({
									method: "ai_expense_claim.api.expense.merge_attachments_by_url",
									args: { url1: existing.custom_attachment, url2: row.custom_attachment }
								});
								if (merged.message) existing.custom_attachment = merged.message;
							} else {
								existing.custom_attachment = row.custom_attachment;
							}
						}
					} else {
						const child = frm.add_child("expenses");
						child.expense_date = row.expense_date;
						child.expense_type = row.expense_type;
						child.amount = row.amount;
						child.description = row.description;
						if (row.custom_attachment) child.custom_attachment = row.custom_attachment;
					}
					form_updated = true;
				}

				frm.refresh_field("expenses");
				frm.dirty();
				applied = true;

				if (!frm.is_new() && frm.doc.name) {
					const keep = [];
					selected.forEach((row) => {
						if (row._attachment_name) keep.push(row._attachment_name);
						else (row._file_doc_names || []).forEach((name) => name && keep.push(name));
					});
					if (keep.length) {
						await frappe.call({
							method: "ai_expense_claim.api.expense.link_files_to_claim",
							args: {
								file_doc_names: JSON.stringify([...new Set(keep)]),
								docname: frm.doc.name
							}
						});
					}
				}

				const selected_names = new Set(selected.map((row) => row.name));
				const leftovers = [];
				(grid.df.data || []).forEach((row) => {
					const source_names = row._file_doc_names || [];
					const merged = row._attachment_name;
					if (!selected_names.has(row.name)) {
						leftovers.push(...source_names);
						if (merged) leftovers.push(merged);
						return;
					}
					if (merged && !source_names.includes(merged)) leftovers.push(...source_names);
				});
				discard_files(leftovers);

				review.hide();
				frappe.show_alert({
					message: frm.is_new()
						? __("{0} expense row(s) added. Save the claim to keep the receipts.", [selected.length])
						: __("{0} expense row(s) added. Save the claim.", [selected.length]),
					indicator: "green"
				});
			} catch (err) {
				console.error(err);
				frappe.show_alert({ message: __("Could not add the expenses. Try again."), indicator: "red" });
			} finally {
				apply_btn.prop("disabled", false).text(__("Add to Expense Claim"));
			}
		},
		secondary_action_label: __("Cancel"),
		secondary_action: () => review.hide(),
		onhide() {
			if (!applied && !form_updated) discard_files(names_from(groups));
		}
	});

	review.$wrapper.addClass("ai-bill-processor-dialog");
	review.show();

	const grid = review.fields_dict.expenses.grid;
	grid.df.data = groups.map((g, idx) => ({
		name: frappe.utils.get_random(10),
		idx: idx + 1,
		doctype: "Expense Claim Detail",
		__checked: 1,
		expense_date: g.expense_date,
		expense_type: g.expense_type,
		amount: g.amount,
		description: g.description,
		custom_attachment: g.attachment_url || "",
		_file_doc_names: g.file_doc_names || [],
		_attachment_name: g.attachment_name || "",
	}));
	grid.refresh();

	requestAnimationFrame(() => {
		grid.grid_rows.forEach(row => {
			if (row.doc) row.doc.__checked = 1;
		});
		grid.wrapper.find(".grid-row-check").prop("checked", true);
	});
}
