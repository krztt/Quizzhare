import asyncio
import subprocess
import sys
from pathlib import Path

import flet as ft

from database import add_material, create_course, get_courses, get_materials, initialize_database
from file_handler import parse_document, parse_quiz


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
        course_form.visible = False
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
        course_form.visible = False
        refresh_courses()

    def show_recent(_=None):
        active_course_id[0] = None
        page_heading.value = "Recent Materials"
        course_grid.controls = [material_tile(material) for material in get_materials()] or [ft.Text("No imported materials yet.", color=ft.Colors.GREY_400)]
        page.update()

    def show_shared(_=None):
        active_course_id[0] = None
        page_heading.value = "Shared with Me"
        course_grid.controls = [ft.Text("Shared materials will appear here.", color=ft.Colors.GREY_400)]
        page.update()

    def open_course_form(_):
        course_form.visible = True
        course_name_field.focus()
        page.update()

    def open_quiz_form(_):
        if active_course_id[0] is None:
            status_text.value = "Create or select a course before adding a quiz."
            page.update()
            return
        course_id = active_course_id[0]
        course_title = page_heading.value
        process = subprocess.Popen(
            [sys.executable, "-m", "components.quiz_creator", str(course_id)],
            cwd=Path(__file__).parent,
        )

        async def refresh_after_creator():
            while process.poll() is None:
                await asyncio.sleep(0.25)
            if active_course_id[0] == course_id:
                select_course(course_id, course_title)
            status_text.value = "Quiz creator closed."
            page.update()

        page.run_task(refresh_after_creator)
        status_text.value = "Opened quiz creator in a separate window."
        page.update()

    sidebar = ft.Container(content=ft.Column([
        ft.Text("P2P Reviewer", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_200),
        ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
        ft.TextButton("My Courses", icon=ft.Icons.FOLDER_SPECIAL, on_click=show_courses),
        ft.TextButton("Recent Materials", icon=ft.Icons.HISTORY, on_click=show_recent),
        ft.TextButton("Shared with Me", icon=ft.Icons.PEOPLE, on_click=show_shared),
        ft.Divider(height=20, color=ft.Colors.GREY_800),
        ft.FilledButton("Import Material", icon=ft.Icons.DOWNLOAD, on_click=import_file),
        ft.FilledButton("Import Quiz", icon=ft.Icons.QUIZ, on_click=import_quiz),
        status_text,
    ]), width=250, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, padding=20)

    page.add(ft.Row([sidebar, ft.Container(content=ft.Column([
        ft.Row([page_heading, ft.Row([
            ft.FilledButton("New Course", icon=ft.Icons.ADD, on_click=open_course_form),
            ft.FilledButton("Add Quiz", icon=ft.Icons.QUIZ, on_click=open_quiz_form),
        ])], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        course_form, ft.Divider(height=20, color=ft.Colors.TRANSPARENT), course_grid,
    ]), expand=True, padding=30)], expand=True, spacing=0))
    refresh_courses()


if __name__ == "__main__":
    ft.run(main)