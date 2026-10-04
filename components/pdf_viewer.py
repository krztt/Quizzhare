import re
import sys
from pathlib import Path

import flet as ft

from file_handler import (
	DocumentSection,
	ParsedDocument,
	annotation_key_for_text,
	parse_document,
	python_index_from_utf16_offset,
	save_reviewer,
)


def empty_document(file_path: str = "") -> ParsedDocument:
	base_name = Path(file_path).stem if file_path else "Untitled reviewer"
	document = ParsedDocument(base_name, "PDF", [DocumentSection("Page 1", ["Start annotating this page."])])
	document.sync_annotations()
	return document


def load_review_document(file_path: str, fallback_title: str | None = None) -> ParsedDocument:
	if not file_path:
		return empty_document(fallback_title or "")
	path = Path(file_path)
	if path.exists():
		return parse_document(str(path))
	if path.suffix.lower() in {".pdf", ".json", ".revx"}:
		return empty_document(str(path))
	return empty_document(fallback_title or "")


def build_view(page: ft.Page, file_path: str = "", on_close=None) -> ft.Control:
	document = load_review_document(file_path)
	status = ft.Text("Ready to review.", color=ft.Colors.GREY_400)
	title_field = ft.TextField(value=document.title, label="Reviewer title", expand=True)
	reviewers_dir = Path(__file__).parent.parent / "assets" / "reviewers"
	reviewer_path = Path(file_path).with_suffix(".revx") if file_path and Path(file_path).suffix.lower() == ".pdf" else Path(file_path) if file_path else reviewers_dir / "Untitled reviewer.revx"
	content_area = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
	highlighter_mode = ft.Ref[ft.Switch]()
	edit_mode = ft.Ref[ft.Switch]()
	content_toolbar = ft.Ref[ft.Row]()
	selection_highlight_button = ft.Ref[ft.TextButton]()
	pending_selection: list[tuple[DocumentSection, int, int, int]] = []

	def remember_selection(event, section: DocumentSection, line_number: int, line: str):
		selected_text = event.selected_text
		if not selected_text:
			return
		start = python_index_from_utf16_offset(line, event.selection.start)
		end = python_index_from_utf16_offset(line, event.selection.end)
		if line[start:end] != selected_text:
			start = line.find(selected_text)
			if start < 0:
				return
			end = start + len(selected_text)
		pending_selection[:] = [(section, line_number, start, end)]
		if selection_highlight_button.current:
			selection_highlight_button.current.disabled = False
			selection_highlight_button.current.update()
		status.value = "Text selected. Choose Highlight selection to apply it."
		status.update()

	def highlight_selection(_):
		if not pending_selection:
			status.value = "Select text in the document before highlighting."
			page.update()
			return
		section, line_number, start, end = pending_selection[0]
		range_key = str(line_number)
		ranges = section.highlight_ranges.setdefault(range_key, [])
		selected_range = (start, end)
		if selected_range in ranges:
			ranges.remove(selected_range)
			if not ranges:
				section.highlight_ranges.pop(range_key, None)
				status.value = f"Removed highlight on {section.heading}."
		else:
			ranges.append(selected_range)
			status.value = f"Highlighted selected text on {section.heading}."
			ranges.sort()
		pending_selection.clear()
		if selection_highlight_button.current:
			selection_highlight_button.current.disabled = True
		document.sync_annotations()
		render_content()

	def render_content():
		content_area.controls.clear()
		
		if not document.sections:
			content_area.controls.append(
				ft.Text("No document sections available.", color=ft.Colors.GREY_400, size=14)
			)
			page.update()
			return

		# Build toolbar
		if not content_toolbar.current:
			toolbar = ft.Row(spacing=10)
			content_toolbar.current = toolbar
		content_toolbar.current.controls = [
			ft.TextButton("Add section", icon=ft.Icons.ADD, on_click=add_section),
		]
		if not (edit_mode.current and edit_mode.current.value):
			content_toolbar.current.controls.append(ft.TextButton(
				"Highlight selection",
				icon=ft.Icons.HIGHLIGHT_ALT,
				on_click=highlight_selection,
				disabled=True,
				ref=selection_highlight_button,
			))
		content_area.controls.append(content_toolbar.current)

		# Build document content
		for section in document.sections:
			document_lines = []
			if edit_mode.current and edit_mode.current.value:
				document_lines.append(ft.TextField(
					label="Section heading",
					value=section.heading,
					dense=True,
					on_change=lambda e, section_ref=section: update_heading(section_ref, e.control.value),
				))
				document_lines.append(ft.TextField(
					label="Reviewer content",
					value="\n".join(section.content),
					multiline=True,
					min_lines=8,
					max_lines=30,
					border=ft.InputBorder.OUTLINE,
					on_change=lambda e, section_ref=section: update_section_content(section_ref, e.control.value),
				))
				document_lines.append(ft.TextButton(
					"Add paragraph",
					icon=ft.Icons.ADD,
					on_click=lambda e, section_ref=section: add_paragraph(section_ref),
				))
			elif len(document.sections) > 1 or section.heading not in {"Document", "Content"}:
				document_lines.append(
					ft.Text(
						section.heading,
						size=16,
						weight=ft.FontWeight.BOLD,
						color=ft.Colors.BLUE_GREY_800,
						text_align=ft.TextAlign.LEFT,
					)
				)
			for line_index, line in enumerate(section.content, start=1) if not (edit_mode.current and edit_mode.current.value) else []:
				line_key = annotation_key_for_text(line) or f"line-{line_index}"
				note_value = section.notes.get(line_key, "")
				is_highlighted = line_key in section.highlights
				highlight_ranges = section.highlight_ranges.get(str(line_index), [])
				text_spans = []
				if highlight_ranges and not is_highlighted:
					position = 0
					for start, end in sorted(highlight_ranges):
						start = max(position, min(start, len(line)))
						end = min(end, len(line))
						if start >= end:
							continue
						if position < start:
							text_spans.append(ft.TextSpan(text=line[position:start]))
						text_spans.append(ft.TextSpan(
							text=line[start:end],
							style=ft.TextStyle(bgcolor=ft.Colors.AMBER_100, color=ft.Colors.BLACK),
						))
						position = end
						if position == len(line):
							break
					if position < len(line):
						text_spans.append(ft.TextSpan(text=line[position:]))
				text_control = ft.Text(
					value=line if not text_spans else "",
					spans=text_spans or None,
					selectable=True,
					on_selection_change=lambda e, section_ref=section, number=line_index, text=line: remember_selection(e, section_ref, number, text),
					size=13,
					weight=ft.FontWeight.W_500,
					color=ft.Colors.BLACK,
					style=ft.TextStyle(
						bgcolor=ft.Colors.AMBER_100 if is_highlighted else None,
						color=ft.Colors.BLACK,
						weight=ft.FontWeight.W_600 if is_highlighted else ft.FontWeight.W_500,
					),
				)
				text_container = ft.Container(
					content=text_control,
					padding=ft.Padding.only(left=2, right=2, top=2, bottom=2),
					on_click=lambda e, section_ref=section, key=line_key: toggle_highlight(section_ref, key, not (key in section_ref.highlights)) if (highlighter_mode.current.value if highlighter_mode.current else False) else None,
				)
				text_block = ft.Column(
					[text_container],
					spacing=4,
				)
				if is_highlighted:
					text_block.controls.append(
						ft.Row([
							ft.TextField(
								label="Note",
								value=note_value,
								dense=True,
								expand=True,
								on_change=lambda e, section_ref=section, key=line_key: update_note(section_ref, key, e.control.value),
							),
							ft.TextButton(
								"Remove",
								icon=ft.Icons.DELETE,
								on_click=lambda e, section_ref=section, key=line_key: toggle_highlight(section_ref, key, False),
							),
						], spacing=10)
					)
				document_lines.append(text_block)
			paper = ft.Container(
				content=ft.Column(document_lines, spacing=10),
				col={"xs": 12, "md": 10, "lg": 8},
				padding=ft.Padding.all(20),
				bgcolor=ft.Colors.WHITE,
				border_radius=8,
				border=ft.Border.all(1, ft.Colors.GREY_300),
				shadow=ft.BoxShadow(
					blur_radius=10,
					color=ft.Colors.GREY_400,
					offset=ft.Offset(0, 2),
					spread_radius=0,
				),
			)
			content_area.controls.append(ft.ResponsiveRow(
				[paper],
				columns=12,
				alignment=ft.MainAxisAlignment.CENTER,
				run_spacing=8,
			))
		
		page.update()

	def update_heading(section: DocumentSection, heading: str):
		section.heading = heading.strip() or "Untitled section"
		document.sync_annotations()

	def update_section_content(section: DocumentSection, content: str):
		section.content = content.splitlines() or [""]
		valid_keys = {annotation_key_for_text(line) for line in section.content}
		section.notes = {key: value for key, value in section.notes.items() if key in valid_keys}
		section.highlights.intersection_update(valid_keys)
		section.highlight_ranges.clear()
		document.sync_annotations()

	def add_paragraph(section: DocumentSection):
		section.content.append("")
		status.value = f"Added a paragraph to {section.heading}."
		render_content()

	def add_section(_):
		document.sections.append(DocumentSection("New section", [""]))
		status.value = "Added a section. Edit its heading and content."
		render_content()

	def toggle_highlighter_mode():
		if highlighter_mode.current:
			highlighter_mode.current.value = not highlighter_mode.current.value
			status.value = f"Highlighter mode {'ON' if highlighter_mode.current.value else 'OFF'}"
			render_content()

	def update_note(section: DocumentSection, line_key: str, note_text: str):
		note_text = note_text.strip()
		if note_text:
			section.notes[line_key] = note_text
		else:
			section.notes.pop(line_key, None)
		document.annotations[section.heading] = dict(section.notes)
		status.value = f"Saved note for {section.heading} marker."
		page.update()
		render_content()

	def toggle_highlight(section: DocumentSection, line_key: str, active: bool):
		if active:
			section.highlights.add(line_key)
		else:
			section.highlights.discard(line_key)
		document.highlights[section.heading] = set(section.highlights)
		status.value = f"{'Highlighted' if active else 'Removed highlight'} on {section.heading}."
		render_content()

	def save_reviewer_file(_):
		nonlocal reviewer_path
		document.title = title_field.value.strip() or document.title
		document.sync_annotations()
		try:
			if not file_path:
				file_name = re.sub(r'[<>:"/\\|?*]+', "-", document.title).strip(" .") or "Untitled reviewer"
				reviewer_path = reviewers_dir / f"{file_name}.revx"
			save_reviewer(document, str(reviewer_path))
			status.value = f"Reviewer saved to {reviewer_path.name}."
		except OSError as error:
			status.value = str(error)
		page.update()

	def load_from_disk(_):
		nonlocal document
		try:
			document = load_review_document(str(reviewer_path)) if reviewer_path.exists() else load_review_document(file_path)
			document.sync_annotations()
			title_field.value = document.title
			status.value = "Loaded the latest reviewer state."
		except (OSError, ValueError) as error:
			status.value = str(error)
		render_content()

	if file_path:
		try:
			document = parse_document(file_path)
			document.sync_annotations()
			title_field.value = document.title
			reviewer_path = Path(file_path).with_suffix(".revx") if Path(file_path).suffix.lower() == ".pdf" else Path(file_path)
		except (OSError, ValueError) as error:
			status.value = str(error)
			document = empty_document(file_path)
			title_field.value = document.title

	toolbar = ft.ResponsiveRow([
		ft.Container(content=title_field, col={"xs": 12, "md": 6}),
		ft.Container(content=ft.Switch(label="Edit content", value=True, ref=edit_mode, on_change=lambda _: render_content()), col={"xs": 6, "sm": 4, "md": 2}),
		ft.Container(content=ft.Switch(label="Highlighter", value=False, ref=highlighter_mode), col={"xs": 6, "sm": 4, "md": 2}),
		ft.Container(content=ft.FilledButton("Save reviewer", icon=ft.Icons.SAVE, on_click=save_reviewer_file), col={"xs": 6, "sm": 4, "md": 1}),
		ft.Container(content=ft.TextButton("Reload", icon=ft.Icons.REFRESH, on_click=load_from_disk), col={"xs": 6, "sm": 4, "md": 1}),
	], spacing=8, run_spacing=8)

	content_panel = ft.Container(
		content=content_area,
		expand=True,
		bgcolor=ft.Colors.GREY_200,
		padding=8,
		border_radius=12,
		alignment=ft.Alignment(0.5, 0.5),
	)

	heading_controls = []
	if on_close:
		heading_controls.append(ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Back", on_click=on_close))
	heading_controls.append(ft.Text("Document Reviewer", size=26, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_900))
	main_layout = ft.Column(
		[
			ft.Row(heading_controls, spacing=8, wrap=True),
			toolbar,
			status,
			ft.Divider(color=ft.Colors.GREY_300),
			content_panel,
		],
		expand=True,
		spacing=12,
		horizontal_alignment=ft.CrossAxisAlignment.CENTER,
	)
	
	render_content()
	return main_layout


def main(page: ft.Page):
	file_path = sys.argv[1] if len(sys.argv) > 1 else ""
	page.title = "Reviewer Studio"
	page.theme_mode = ft.ThemeMode.LIGHT
	page.bgcolor = ft.Colors.GREY_200
	page.padding = 12
	page.add(build_view(page, file_path, lambda _: page.window.close()))
	page.update()


if __name__ == "__main__":
	ft.run(main)
