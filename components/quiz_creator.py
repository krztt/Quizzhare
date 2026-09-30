import json
import sys
from pathlib import Path

import flet as ft

from database import add_material


def main(page: ft.Page):
    if len(sys.argv) < 2:
        page.add(ft.Text("A course must be selected before creating a quiz."))
        return

    course_id = int(sys.argv[1])
    page.title = "Create Quiz"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16

    title_field = ft.TextField(label="Quiz title", autofocus=True)
    question_rows = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    status_text = ft.Text(color=ft.Colors.RED_300, size=12)

    def add_question_row(_=None):
        question_field = ft.TextField(label="Question", expand=True)
        type_field = ft.Dropdown(
            label="Type",
            value="multiple_choice",
            options=[
                ft.dropdown.Option("multiple_choice", "Multiple choice"),
                ft.dropdown.Option("identification", "Identification"),
            ],
        )
        option_fields = [
            ft.TextField(label=f"Option {index}", expand=True)
            for index in range(1, 5)
        ]
        options_row = ft.ResponsiveRow([
            ft.Container(content=option_field, col={"xs": 12, "sm": 6, "lg": 3})
            for option_field in option_fields
        ], spacing=8, run_spacing=8)
        answer_field = ft.TextField(label="Correct answer", expand=True)
        delete_button = ft.IconButton(ft.Icons.DELETE, tooltip="Remove question")

        def change_type(_):
            options_row.visible = type_field.value == "multiple_choice"
            if not options_row.visible:
                for option_field in option_fields:
                    option_field.value = ""
            page.update()

        type_field.on_select = change_type
        row = ft.Container(
            content=ft.Column([
                ft.ResponsiveRow([
                    ft.Container(content=type_field, col={"xs": 12, "sm": 4}),
                    ft.Container(content=question_field, col={"xs": 10, "sm": 7}),
                    ft.Container(content=delete_button, col={"xs": 2, "sm": 1}),
                ], spacing=8, run_spacing=8),
                options_row,
                answer_field,
            ], spacing=8),
            padding=12,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
        )

        def remove_row(_):
            question_rows.controls.remove(row)
            page.update()

        delete_button.on_click = remove_row
        question_rows.controls.append(row)
        page.update()

    def save_quiz(_):
        title = (title_field.value or "").strip()
        questions = []
        for row in question_rows.controls:
            fields = row.content.controls
            type_field = fields[0].controls[0].content
            question_field = fields[0].controls[1].content
            options_row = fields[1]
            answer_field = fields[2]
            question = (question_field.value or "").strip()
            answer = (answer_field.value or "").strip()
            options = [
                (option_container.content.value or "").strip()
                for option_container in options_row.controls
                if (option_container.content.value or "").strip()
            ]
            if not question or not answer:
                status_text.value = "Every question needs text and an answer."
                page.update()
                return
            if type_field.value == "multiple_choice" and (len(options) < 2 or answer not in options):
                status_text.value = "Multiple-choice questions need two options and a matching answer."
                page.update()
                return
            question_data = {"type": type_field.value, "question": question, "answer": answer}
            if type_field.value == "multiple_choice":
                question_data["options"] = options
            questions.append(question_data)

        if not title or not questions:
            status_text.value = "Add a quiz title and at least one question."
            page.update()
            return

        export_dir = Path(__file__).parent.parent / "assets" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        quiz_path = export_dir / f"{title}.json"
        quiz_path.write_text(
            json.dumps({"title": title, "questions": questions}, indent=2),
            encoding="utf-8",
        )
        add_material(course_id, title, "quiz", str(quiz_path))
        page.window.close()

    add_question_row()
    page.add(ft.Column([
        ft.Text("Create Quiz", size=26, weight=ft.FontWeight.BOLD),
        title_field,
        ft.Row([
            ft.Text("Questions", size=18, weight=ft.FontWeight.BOLD),
            ft.TextButton("Add question", icon=ft.Icons.ADD, on_click=add_question_row),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
        question_rows,
        status_text,
        ft.Row([
            ft.FilledButton("Save Quiz", icon=ft.Icons.SAVE, on_click=save_quiz),
            ft.TextButton("Cancel", on_click=lambda _: page.window.close()),
        ], wrap=True),
    ], expand=True, spacing=12, scroll=ft.ScrollMode.AUTO))


if __name__ == "__main__":
    ft.run(main)