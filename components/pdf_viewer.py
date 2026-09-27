import sys
from pathlib import Path

import flet as ft

from file_handler import DocumentSection, ParsedDocument, annotation_key_for_text, parse_document, save_reviewer


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


def main(page: ft.Page):
	file_path = sys.argv[1] if len(sys.argv) > 1 else ""
	page.title = "Reviewer Studio"
	page.theme_mode = ft.ThemeMode.LIGHT
	page.bgcolor = ft.Colors.GREY_200
	page.window.width = 1200
	page.window.height = 800
	page.padding = 0

	document = load_review_document(file_path)
	status = ft.Text("Ready to review.", color=ft.Colors.GREY_400)
	title_field = ft.TextField(value=document.title, label="Reviewer title", expand=True)
	reviewer_path = Path(file_path).with_suffix(".revx") if file_path and Path(file_path).suffix.lower() == ".pdf" else Path("untitled_reviewer.revx")
	content_area = ft.Column(spacing=10, height=620, width=860, scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
	highlighter_mode = ft.Ref[ft.Switch]()
	content_toolbar = ft.Ref[ft.Row]()

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
			toolbar = ft.Row([ft.TextButton(
				"Highlight",
				icon=ft.Icons.HIGHLIGHT_ALT,
				on_click=lambda e: toggle_highlighter_mode(),
			)], spacing=10)
			content_toolbar.current = toolbar
		
		content_area.controls.append(content_toolbar.current)

		# Build document content
		for section in document.sections:
			document_lines = []
			if len(document.sections) > 1 or section.heading not in {"Document", "Content"}:
				document_lines.append(
					ft.Text(
						section.heading,
						size=16,
						weight=ft.FontWeight.BOLD,
						color=ft.Colors.BLUE_GREY_800,
						text_align=ft.TextAlign.LEFT,
					)
				)
			for line_index, line in enumerate(section.content, start=1):
				line_key = annotation_key_for_text(line) or f"line-{line_index}"
				note_value = section.notes.get(line_key, "")
				is_highlighted = line_key in section.highlights
				text_control = ft.Text(
					line,
					selectable=True,
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
				width=760,
				padding=ft.Padding.all(44),
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
			content_area.controls.append(ft.Container(content=paper, alignment=ft.Alignment(0.5, 0.5), padding=ft.Padding.only(top=8, bottom=8)))
		
		content_area.update()
		page.update()

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
		document.title = title_field.value.strip() or document.title
		document.sync_annotations()
		try:
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

	toolbar = ft.Row([
		title_field,
		ft.Switch(label="Highlighter", value=False, ref=highlighter_mode),
		ft.FilledButton("Save reviewer", icon=ft.Icons.SAVE, on_click=save_reviewer_file),
		ft.TextButton("Reload", icon=ft.Icons.REFRESH, on_click=load_from_disk),
	], spacing=12, expand=True, wrap=True)

	content_panel = ft.Container(
		content=content_area,
		height=620,
		width=900,
		bgcolor=ft.Colors.GREY_200,
		padding=8,
		border_radius=12,
		alignment=ft.Alignment(0.5, 0.5),
	)

	main_layout = ft.Column(
		[
			ft.Text("Document Reviewer", size=26, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_900),
			toolbar,
			status,
			ft.Divider(color=ft.Colors.GREY_300),
			content_panel,
		],
		height=720,
		width=1160,
		spacing=12,
		horizontal_alignment=ft.CrossAxisAlignment.CENTER,
	)
	
	page.add(main_layout)
	page.update()
	content_area.update()
	render_content()


if __name__ == "__main__":
	ft.run(main)
