import json
from pathlib import Path

from file_handler import (
    annotation_key_for_text,
    flatten_pdf_pages_to_document,
    parse_document,
    python_index_from_utf16_offset,
    save_reviewer,
)
import database


def test_annotation_key_for_text_normalizes_selection_text():
    assert annotation_key_for_text("  Alpha   beta gamma  ") == "Alpha beta gamma"


def test_utf16_selection_offsets_convert_to_python_indexes():
    assert python_index_from_utf16_offset("A😀BC", 3) == 2


def test_parse_document_supports_reviewer_annotations(tmp_path):
    path = tmp_path / "sample.revx"
    payload = {
        "title": "Sample reviewer",
        "sections": [
            {
                "heading": "Page 1",
                "content": ["Alpha", "Beta", "Gamma"],
                "notes": {"1": "Focus here", "2": "Check this line"},
                "highlights": ["2"],
                "highlight_ranges": {"1": [[0, 5]]},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    document = parse_document(str(path))

    assert document.title == "Sample reviewer"
    assert document.sections[0].heading == "Page 1"
    assert document.sections[0].content[1] == "Beta"
    assert document.annotations["Page 1"]["Alpha"] == "Focus here"
    assert document.annotations["Page 1"]["Beta"] == "Check this line"
    assert document.highlights["Page 1"] == {"Beta"}
    assert document.sections[0].highlight_ranges == {"1": [(0, 5)]}

    saved_path = tmp_path / "roundtrip.revx"
    save_reviewer(document, str(saved_path))
    assert parse_document(str(saved_path)).sections[0].highlight_ranges == {"1": [(0, 5)]}


def test_flatten_pdf_pages_to_document_creates_one_word_like_section():
    sections = flatten_pdf_pages_to_document([
        "First paragraph for the document.",
        "Second paragraph continues the flow.",
    ])

    assert len(sections) == 1
    assert sections[0].heading == "Document"
    assert sections[0].content == [
        "First paragraph for the document.",
        "Second paragraph continues the flow.",
    ]


def test_course_and_material_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.initialize_database()

    course_id = database.create_course("Biology")
    database.add_material(course_id, "Cell Quiz", "quiz", "cell-quiz.json")
    material_id = database.get_materials(course_id)[0][0]

    assert database.rename_course(course_id, "  Biology II  ")
    assert database.get_courses()[0][1] == "Biology II"
    assert database.update_material(material_id, "  Cells Quiz  ")
    assert database.get_materials(course_id)[0][2] == "Cells Quiz"
    assert database.delete_material(material_id)
    assert database.get_materials(course_id) == []

    database.add_material(course_id, "Genetics Quiz", "quiz", "genetics.json")
    assert database.delete_course(course_id)
    assert database.get_courses() == []
    assert database.get_materials() == []
