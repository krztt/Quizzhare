import json
import sys

import flet as ft


def main(page: ft.Page):
	page.title = "Quiz"
	page.theme_mode = ft.ThemeMode.DARK
	page.window.width = 760
	page.window.height = 700
	page.padding = 28

	try:
		with open(sys.argv[1], encoding="utf-8") as quiz_file:
			quiz = json.load(quiz_file)
	except (IndexError, OSError, json.JSONDecodeError) as error:
		page.add(ft.Text(f"Unable to open quiz: {error}", color=ft.Colors.RED_300))
		return

	score = [0]
	current = [0]
	submitted = [False]
	result = ft.Text()
	question_area = ft.Column(spacing=14)

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
			ft.Text(question["question"], size=22, weight=ft.FontWeight.BOLD),
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

	page.add(ft.Column([
		ft.Text(quiz.get("title", "Quiz"), size=28, weight=ft.FontWeight.BOLD),
		ft.Divider(),
		question_area,
	], expand=True))
	render_question()


if __name__ == "__main__":
	ft.run(main)
