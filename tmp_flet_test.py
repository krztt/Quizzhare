import flet as ft

def main(page: ft.Page):
    page.title = 'Test'
    page.bgcolor = ft.Colors.BLACK
    page.padding = 20
    page.add(
        ft.Column([
            ft.Text('HELLO WORLD', size=30, color=ft.Colors.WHITE),
            ft.Text('SECOND LINE', color=ft.Colors.WHITE),
        ], spacing=10)
    )
    page.update()

ft.run(main)
