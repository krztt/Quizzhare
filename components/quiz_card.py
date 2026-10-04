import json
import sys

import flet as ft


def build_view(page: ft.Page, file_path: str, on_close=None) -> ft.Control:
	try:
		with open(file_path, encoding="utf-8") as quiz_file:
			quiz = json.load(quiz_file)
	except (IndexError, OSError, json.JSONDecodeError) as error:
		return ft.Column([
			ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Back", on_click=on_close),
			ft.Text(f"Unable to open quiz: {error}", color=ft.Colors.RED_300),
		])

	score = [0]
	current = [0]
	submitted = [False]
	result = ft.Text()
	question_area = ft.Column(spacing=14, expand=True)

	def render_question():
		submitted[0] = False
		question = quiz["questions"][current[0]]
		if question.get("type", "multiple_choice") == "identification":
			answer_control = ft.TextField(label="Your answer")
		else:
			answer_control = ft.RadioGroup(
				content=ft.Column([ft.Radio(value=option, label=option) for option in question["options"]])
			)
		submit_button = ft.FilledButton(
			"Submit answer",
			icon=ft.Icons.CHECK,
			on_click=lambda _: submit(answer_control, submit_button),
		)
		question_area.controls = [
			ft.Text(f"Question {current[0] + 1} of {len(quiz['questions'])}", color=ft.Colors.GREY_400),
			ft.Text(question["question"], size=20, weight=ft.FontWeight.BOLD),
			answer_control,
			submit_button,
			result,
		]
		page.update()

	def submit(options, submit_button):
		if submitted[0]:
			return
		answer = (options.value or "").strip()
		if not answer:
			result.value = "Choose an answer first."
			page.update()
			return
		submitted[0] = True
		submit_button.disabled = True
		question = quiz["questions"][current[0]]
		if answer.casefold() == question["answer"].strip().casefold():
			score[0] += 1
			result.value = "Correct!"
		else:
			result.value = f"Incorrect. Correct answer: {question['answer']}"
		if current[0] + 1 < len(quiz["questions"]):
			question_area.controls.append(
				ft.FilledButton("Next question", on_click=lambda _: next_question())
			)
		else:
			question_area.controls.append(ft.Text(f"Score: {score[0]} / {len(quiz['questions'])}"))
		page.update()

	def next_question():
		current[0] += 1
		render_question()

	controls = []
	if on_close:
		controls.append(ft.IconButton(ft.Icons.ARROW_BACK, tooltip="Back", on_click=on_close))
	controls.extend([
		ft.Text(quiz.get("title", "Quiz"), size=24, weight=ft.FontWeight.BOLD),
		ft.Divider(),
		question_area,
	])
	view = ft.Column(controls, expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
	render_question()
	return view


def main(page: ft.Page):
	page.title = "Quiz"
	page.theme_mode = ft.ThemeMode.DARK
	page.padding = 16
	file_path = sys.argv[1] if len(sys.argv) > 1 else ""
	page.add(build_view(page, file_path, lambda _: page.window.close()))
	page.update()


if __name__ == "__main__":
	ft.run(main)
