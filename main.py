import json
import re
import subprocess
import sys
from pathlib import Path

import flet as ft

from database import add_material, create_course, get_courses, get_materials, initialize_database
from file_handler import DocumentSection, ParsedDocument, parse_document, parse_quiz, save_reviewer


def main(page: ft.Page):
    page.title = "Peer-to-Peer Reviewer"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1200
    page.window.height = 800
    page.padding = 0
    initialize_database()

    active_course_id = [None]
    status_text = ft.Text("Ready.", color=ft.Colors.GREY_400, size=12)
    page_heading = ft.Text("My Courses", size=28, weight=ft.FontWeight.W_800)
    course_grid = ft.GridView(height=520, runs_count=5, max_extent=280, child_aspect_ratio=1.6, spacing=20, run_spacing=20)
    file_picker = ft.FilePicker()

    def launch_viewer(file_path, material_type):
        module = "components.quiz_card" if material_type == "quiz" else "components.pdf_viewer"
        subprocess.Popen([sys.executable, "-m", module, file_path], cwd=Path(__file__).parent)
        status_text.value = "Opened material in a separate window."
        page.update()

    def material_tile(material):
        return ft.ListTile(
            leading=ft.Icon(ft.Icons.QUIZ if material[3] == "quiz" else ft.Icons.DESCRIPTION),
            title=ft.Text(material[2]), subtitle=ft.Text(material[3].upper()),
            on_click=lambda _, path=material[4], kind=material[3]: launch_viewer(path, kind),
        )

    def select_course(course_id, course_title):
        active_course_id[0] = course_id
        page_heading.value = course_title
        course_actions.visible = True
        course_form.visible = False
        reviewer_maker_panel.visible = False
        quiz_maker_panel.visible = False
        course_grid.visible = True
        course_grid.controls = [material_tile(material) for material in get_materials(course_id)]
        if not course_grid.controls:
            course_grid.controls = [ft.Text("No materials in this course yet.", color=ft.Colors.GREY_400)]
        page.update()

    def create_course_card(course_id, course_title):
        return ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.FOLDER, color=ft.Colors.WHITE, size=30),
                ft.Text(course_title, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(f"{len(get_materials(course_id))} material(s)", size=12, color=ft.Colors.WHITE70),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            width=260, height=160, bgcolor=ft.Colors.BLUE_700, border_radius=12, padding=15, ink=True,
            on_click=lambda _, cid=course_id, title=course_title: select_course(cid, title),
        )

    def refresh_courses():
        course_grid.controls = [create_course_card(course[0], course[1]) for course in get_courses()]
        if not course_grid.controls:
            course_grid.controls = [ft.Text("No courses yet. Create one to get started.", color=ft.Colors.GREY_400)]
        page.update()

    course_name_field = ft.TextField(label="Course name", dense=True, expand=True)
    course_form = ft.Row(visible=False)
    reviewer_title_field = ft.TextField(label="Reviewer title", autofocus=True)
    reviewer_sections = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
    reviewer_section_fields = []
    reviewer_maker_panel = ft.Column(visible=False, expand=True, spacing=12)
    maker_return_heading = ["My Courses"]
    quiz_title_field = ft.TextField(label="Quiz title", autofocus=True)
    quiz_question_rows = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    quiz_question_fields = []
    quiz_maker_panel = ft.Column(visible=False, expand=True, spacing=12)
    quiz_course = [None, ""]
    quiz_status = ft.Text(color=ft.Colors.RED_300, size=12)

    def add_reviewer_section(_=None):
        heading_field = ft.TextField(label="Section heading", value=f"Section {len(reviewer_section_fields) + 1}")
        content_field = ft.TextField(
            label="Reviewer content",
            multiline=True,
            min_lines=6,
            max_lines=18,
            border=ft.InputBorder.OUTLINE,
        )
        reviewer_section_fields.append((heading_field, content_field))
        reviewer_sections.controls.append(ft.Container(
            content=ft.Column([heading_field, content_field], spacing=8),
            padding=12,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
        ))
        page.update()

    def close_reviewer_maker(_=None):
        reviewer_maker_panel.visible = False
        course_grid.visible = True
        page_heading.value = maker_return_heading[0]
        page.update()

    def save_new_reviewer(_):
        title = (reviewer_title_field.value or "").strip()
        sections = [
            DocumentSection(
                heading_field.value.strip() or f"Section {index}",
                content_field.value.splitlines() or [""],
            )
            for index, (heading_field, content_field) in enumerate(reviewer_section_fields, start=1)
        ]
        if not title or not any(any(line.strip() for line in section.content) for section in sections):
            status_text.value = "Enter a reviewer title and add some content."
            page.update()
            return

        document = ParsedDocument(title, "REVX", sections)
        document.sync_annotations()
        file_name = re.sub(r'[<>:"/\\|?*]+', "-", title).strip(" .") or "Untitled reviewer"
        reviewer_path = Path(__file__).parent / "assets" / "reviewers" / f"{file_name}.revx"
        try:
            save_reviewer(document, str(reviewer_path))
            if active_course_id[0] is not None:
                add_material(active_course_id[0], title, "revx", str(reviewer_path))
                status_text.value = f"Saved reviewer and added it to {maker_return_heading[0]}."
                close_reviewer_maker()
                select_course(active_course_id[0], page_heading.value)
            else:
                status_text.value = f"Saved reviewer to {reviewer_path.name}."
                close_reviewer_maker()
        except OSError as error:
            status_text.value = str(error)
            page.update()

    def open_reviewer_maker(_):
        maker_return_heading[0] = page_heading.value
        reviewer_title_field.value = ""
        reviewer_section_fields.clear()
        reviewer_sections.controls.clear()
        add_reviewer_section()
        course_form.visible = False
        quiz_maker_panel.visible = False
        course_grid.visible = False
        reviewer_maker_panel.visible = True
        page_heading.value = "Create Reviewer"
        page.update()

    reviewer_maker_panel.controls = [
        reviewer_title_field,
        ft.Row([
            ft.Text("Sections", size=18, weight=ft.FontWeight.BOLD),
            ft.TextButton("Add section", icon=ft.Icons.ADD, on_click=add_reviewer_section),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        reviewer_sections,
        ft.Row([
            ft.FilledButton("Save Reviewer", icon=ft.Icons.SAVE, on_click=save_new_reviewer),
            ft.TextButton("Cancel", on_click=close_reviewer_maker),
        ]),
    ]

    def add_quiz_question(_=None):
        question_field = ft.TextField(label="Question", expand=True)
        type_field = ft.Dropdown(
            label="Type",
            value="multiple_choice",
            options=[
                ft.dropdown.Option("multiple_choice", "Multiple choice"),
                ft.dropdown.Option("identification", "Identification"),
            ],
            width=180,
        )
        option_fields = [ft.TextField(label=f"Option {index}", expand=True) for index in range(1, 5)]
        options_row = ft.Row(option_fields)
        answer_field = ft.TextField(label="Correct answer", expand=True)
        row = ft.Container(
            content=ft.Column([
                ft.Row([type_field, question_field, ft.IconButton(ft.Icons.DELETE, tooltip="Remove question")]),
                options_row,
                answer_field,
            ], spacing=8),
            padding=12,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
        )

        def change_type(_):
            options_row.visible = type_field.value == "multiple_choice"
            page.update()

        def remove_question(_):
            quiz_question_rows.controls.remove(row)
            quiz_question_fields.remove(question_data)
            page.update()

        type_field.on_change = change_type
        row.content.controls[0].controls[-1].on_click = remove_question
        question_data = {
            "question": question_field,
            "type": type_field,
            "options": option_fields,
            "answer": answer_field,
        }
        quiz_question_fields.append(question_data)
        quiz_question_rows.controls.append(row)
        page.update()

    def close_quiz_maker(_=None):
        quiz_maker_panel.visible = False
        course_grid.visible = True
        page_heading.value = quiz_course[1]
        page.update()

    def save_new_quiz(_):
        title = (quiz_title_field.value or "").strip()
        questions = []
        for index, fields in enumerate(quiz_question_fields, start=1):
            question = (fields["question"].value or "").strip()
            answer = (fields["answer"].value or "").strip()
            options = [(field.value or "").strip() for field in fields["options"] if (field.value or "").strip()]
            if not question or not answer:
                quiz_status.value = f"Question {index} needs text and an answer."
                page.update()
                return
            if fields["type"].value == "multiple_choice" and (len(options) < 2 or answer not in options):
                quiz_status.value = f"Question {index} needs two options and a matching correct answer."
                page.update()
                return
            question_data = {
                "type": fields["type"].value,
                "question": question,
                "answer": answer,
            }
            if fields["type"].value == "multiple_choice":
                question_data["options"] = options
            questions.append(question_data)

        if not title or not questions:
            quiz_status.value = "Add a quiz title and at least one question."
            page.update()
            return

        file_name = re.sub(r'[<>:"/\\|?*]+', "-", title).strip(" .") or "Untitled quiz"
        quiz_path = Path(__file__).parent / "assets" / "exports" / f"{file_name}.json"
        quiz_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            quiz_path.write_text(json.dumps({"title": title, "questions": questions}, indent=2), encoding="utf-8")
            add_material(quiz_course[0], title, "quiz", str(quiz_path))
        except OSError as error:
            quiz_status.value = str(error)
            page.update()
            return

        saved_course_id, saved_course_title = quiz_course
        close_quiz_maker()
        select_course(saved_course_id, saved_course_title)
        status_text.value = f"Saved quiz to {saved_course_title}."
        page.update()

    def open_quiz_form_inline(_):
        if active_course_id[0] is None:
            status_text.value = "Create or select a course before adding a quiz."
            page.update()
            return
        quiz_course[:] = [active_course_id[0], page_heading.value]
        quiz_title_field.value = ""
        quiz_question_fields.clear()
        quiz_question_rows.controls.clear()
        quiz_status.value = ""
        add_quiz_question()
        reviewer_maker_panel.visible = False
        course_form.visible = False
        course_grid.visible = False
        quiz_maker_panel.visible = True
        page_heading.value = "Create Quiz"
        page.update()

    quiz_maker_panel.controls = [
        quiz_title_field,
        ft.Row([
            ft.Text("Questions", size=18, weight=ft.FontWeight.BOLD),
            ft.TextButton("Add question", icon=ft.Icons.ADD, on_click=add_quiz_question),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        quiz_question_rows,
        quiz_status,
        ft.Row([
            ft.FilledButton("Save Quiz", icon=ft.Icons.SAVE, on_click=save_new_quiz),
            ft.TextButton("Cancel", on_click=close_quiz_maker),
        ]),
    ]

    def close_course_form():
        course_name_field.value = ""
        course_form.visible = False
        page.update()

    def add_new_course(_):
        name = (course_name_field.value or "").strip()
        if not name:
            status_text.value = "Enter a course name."
        elif any(course[1].casefold() == name.casefold() for course in get_courses()):
            status_text.value = "A course with that name already exists."
        else:
            create_course(name)
            close_course_form()
            status_text.value = f"Created course: {name}"
            refresh_courses()
            return
        page.update()

    course_form.controls = [course_name_field, ft.FilledButton("Add", icon=ft.Icons.CHECK, on_click=add_new_course), ft.TextButton("Cancel", on_click=lambda _: close_course_form())]

    async def import_file(_):
        files = await file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["revx", "json", "pdf"])
        if not files:
            status_text.value = "Import cancelled."
        elif active_course_id[0] is None:
            status_text.value = "Create or select a course before importing material."
        else:
            try:
                document = parse_document(files[0].path)
                add_material(active_course_id[0], document.title, document.file_type.lower(), files[0].path)
                status_text.value = f"Imported material: {document.title}"
                select_course(active_course_id[0], page_heading.value)
            except (OSError, ValueError) as error:
                status_text.value = str(error)
        page.update()

    async def import_quiz(_):
        files = await file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["json", "revx"])
        if not files:
            status_text.value = "Quiz import cancelled."
        elif active_course_id[0] is None:
            status_text.value = "Create or select a course before importing a quiz."
        else:
            try:
                quiz = parse_quiz(files[0].path)
                add_material(active_course_id[0], quiz["title"], "quiz", files[0].path)
                status_text.value = f"Imported quiz: {quiz['title']}"
                select_course(active_course_id[0], page_heading.value)
            except (OSError, ValueError) as error:
                status_text.value = str(error)
        page.update()

    def show_courses(_=None):
        active_course_id[0] = None
        page_heading.value = "My Courses"
        course_actions.visible = False
        course_form.visible = False
        reviewer_maker_panel.visible = False
        quiz_maker_panel.visible = False
        course_grid.visible = True
        refresh_courses()

    def show_recent(_=None):
        active_course_id[0] = None
        page_heading.value = "Recent Materials"
        course_actions.visible = False
        reviewer_maker_panel.visible = False
        quiz_maker_panel.visible = False
        course_grid.visible = True
        course_grid.controls = [material_tile(material) for material in get_materials()] or [ft.Text("No imported materials yet.", color=ft.Colors.GREY_400)]
        page.update()

    def show_shared(_=None):
        active_course_id[0] = None
        page_heading.value = "Shared with Me"
        course_actions.visible = False
        reviewer_maker_panel.visible = False
        quiz_maker_panel.visible = False
        course_grid.visible = True
        course_grid.controls = [ft.Text("Shared materials will appear here.", color=ft.Colors.GREY_400)]
        page.update()

    def open_course_form(_):
        active_course_id[0] = None
        page_heading.value = "My Courses"
        course_actions.visible = False
        reviewer_maker_panel.visible = False
        quiz_maker_panel.visible = False
        course_grid.visible = True
        course_form.visible = True
        course_name_field.focus()
        page.update()

    def open_quiz_form(_):
        open_quiz_form_inline(_)

    course_actions = ft.Row([
        ft.FilledButton("New Course", icon=ft.Icons.ADD, on_click=open_course_form),
        ft.FilledButton("Add Quiz", icon=ft.Icons.QUIZ, on_click=open_quiz_form),
        ft.FilledButton("Create Reviewer", icon=ft.Icons.EDIT_DOCUMENT, on_click=open_reviewer_maker),
    ], visible=False)

    sidebar = ft.Container(content=ft.Column([
        ft.Text("P2P Reviewer", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_200),
        ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
        ft.TextButton("My Courses", icon=ft.Icons.FOLDER_SPECIAL, on_click=show_courses),
        ft.TextButton("Create course", icon=ft.Icons.ADD, on_click=open_course_form),
        ft.TextButton("Recent Materials", icon=ft.Icons.HISTORY, on_click=show_recent),
        ft.TextButton("Shared with Me", icon=ft.Icons.PEOPLE, on_click=show_shared),
        ft.Divider(height=20, color=ft.Colors.GREY_800),
        ft.FilledButton("Import Material", icon=ft.Icons.DOWNLOAD, on_click=import_file),
        ft.FilledButton("Import Quiz", icon=ft.Icons.QUIZ, on_click=import_quiz),
        status_text,
    ]), width=250, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, padding=20)

    page.add(ft.Row([sidebar, ft.Container(content=ft.Column([
        ft.Row([page_heading, ft.Row([
            course_actions,
        ])], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        course_form, reviewer_maker_panel, quiz_maker_panel,
        ft.Divider(height=20, color=ft.Colors.TRANSPARENT), course_grid,
    ]), expand=True, padding=30)], expand=True, spacing=0))
    refresh_courses()


if __name__ == "__main__":
    ft.run(main)