import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def flatten_pdf_pages_to_document(page_texts: list[str]) -> list["DocumentSection"]:
    """Convert PDF pages into a single flowing document section like a Word page."""
    paragraphs: list[str] = []
    for page_text in page_texts:
        cleaned = (page_text or "").strip()
        if not cleaned:
            continue
        page_paragraphs = [part.strip() for part in cleaned.splitlines() if part.strip()]
        if page_paragraphs:
            paragraphs.extend(page_paragraphs)
    if not paragraphs:
        return [DocumentSection("Document", ["No readable text was found."])]
    return [DocumentSection("Document", paragraphs)]


def annotation_key_for_text(text: str) -> str:
    """Normalize selected text so notes/highlights behave like Word annotations."""
    normalized = " ".join((text or "").split())
    return normalized.strip()


def python_index_from_utf16_offset(text: str, offset: int) -> int:
	"""Convert a Flutter UTF-16 selection offset to a Python string index."""
	consumed = 0
	for index, character in enumerate(text):
		if consumed >= offset:
			return index
		consumed += 2 if ord(character) > 0xFFFF else 1
	return len(text)


def normalize_annotation_map(values: dict[str, str] | Any, content: list[str] | None = None) -> dict[str, str]:
    """Convert numeric review keys to the visible text they annotate."""
    if not isinstance(values, dict):
        return {}
    normalized: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key_text = annotation_key_for_text(str(raw_key))
        if key_text.isdigit() and content:
            index = int(key_text) - 1
            if 0 <= index < len(content):
                key_text = annotation_key_for_text(content[index])
        if key_text:
            normalized[key_text] = str(raw_value)
    return normalized


@dataclass
class DocumentSection:
	heading: str
	content: list[str]
	notes: dict[str, str] = field(default_factory=dict)
	highlights: set[str] = field(default_factory=set)
	highlight_ranges: dict[str, list[tuple[int, int]]] = field(default_factory=dict)


@dataclass
class ParsedDocument:
	title: str
	file_type: str
	sections: list[DocumentSection]
	annotations: dict[str, dict[str, str]] = field(default_factory=dict)
	highlights: dict[str, set[str]] = field(default_factory=dict)
	source_path: str = ""

	def sync_annotations(self):
		self.annotations = {}
		self.highlights = {}
		for section in self.sections:
			self.annotations[section.heading] = dict(section.notes)
			self.highlights[section.heading] = set(section.highlights)


def parse_quiz(file_path: str) -> dict:
	"""Load and validate the quiz format used by the quiz window."""
	path = Path(file_path)
	try:
		data = json.loads(path.read_text(encoding="utf-8"))
	except json.JSONDecodeError as error:
		raise ValueError(f"Invalid quiz JSON in {path.name}: {error.msg}") from error

	if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
		raise ValueError("A quiz must contain a questions list.")
	if not data["questions"]:
		raise ValueError("A quiz must contain at least one question.")

	for index, question in enumerate(data["questions"], start=1):
		if not isinstance(question, dict):
			raise ValueError(f"Question {index} must be an object.")
		question_type = question.get("type", "multiple_choice")
		if not question.get("question") or question_type not in {"multiple_choice", "identification"}:
			raise ValueError(f"Question {index} needs text and a valid type.")
		if question_type == "multiple_choice":
			if not isinstance(question.get("options"), list) or len(question["options"]) < 2:
				raise ValueError(f"Question {index} needs at least two options.")
			if question.get("answer") not in question["options"]:
				raise ValueError(f"Question {index} needs a valid answer.")
		elif not isinstance(question.get("answer"), str) or not question["answer"].strip():
			raise ValueError(f"Question {index} needs an answer.")
		question["type"] = question_type

	data.setdefault("title", path.stem)
	return data


def parse_document(file_path: str) -> ParsedDocument:
	"""Parse a supported reviewer file into display-ready sections."""
	path = Path(file_path)
	suffix = path.suffix.lower()

	if suffix in {".json", ".revx"}:
		return _parse_json_document(path)
	if suffix == ".pdf":
		return _parse_pdf_document(path)
	raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")


def _parse_json_document(path: Path) -> ParsedDocument:
	try:
		data = json.loads(path.read_text(encoding="utf-8"))
	except json.JSONDecodeError as error:
		raise ValueError(f"Invalid JSON in {path.name}: {error.msg}") from error

	sections = _organize_value(data)
	if isinstance(data, dict) and isinstance(data.get("sections"), list):
		sections = []
		for index, section_data in enumerate(data["sections"], start=1):
			if not isinstance(section_data, dict):
				continue
			heading = str(section_data.get("heading") or f"Section {index}")
			content = section_data.get("content") or []
			if isinstance(content, str):
				content = [content]
			content = [str(item) for item in content]
			notes = normalize_annotation_map(section_data.get("notes") or {}, content)
			highlights_raw = section_data.get("highlights") or []
			highlights = set()
			if isinstance(highlights_raw, str):
				highlights = {annotation_key_for_text(highlights_raw)}
			elif isinstance(highlights_raw, (list, tuple, set)):
				highlights = {annotation_key_for_text(str(item)) for item in highlights_raw if str(item).strip()}
			if highlights:
				highlights = {
					annotation_key_for_text(content[int(item)-1]) if item.isdigit() and 0 < int(item) <= len(content) else annotation_key_for_text(str(item))
					for item in highlights
				}
			highlight_ranges = {}
			raw_highlight_ranges = section_data.get("highlight_ranges")
			if not isinstance(raw_highlight_ranges, dict):
				raw_highlight_ranges = {}
			for raw_line_number, raw_ranges in raw_highlight_ranges.items():
				if not str(raw_line_number).isdigit():
					continue
				line_number = int(raw_line_number)
				if not 0 < line_number <= len(content) or not isinstance(raw_ranges, list):
					continue
				line = content[line_number - 1]
				valid_ranges = []
				for raw_range in raw_ranges:
					if not isinstance(raw_range, list) or len(raw_range) != 2:
						continue
					start, end = raw_range
					if type(start) is int and type(end) is int and 0 <= start < end <= len(line):
						valid_ranges.append((start, end))
				if valid_ranges:
					highlight_ranges[str(line_number)] = valid_ranges
			sections.append(DocumentSection(
				heading,
				content or ["Empty section"],
				notes=notes,
				highlights=highlights,
				highlight_ranges=highlight_ranges,
			))
		if not sections:
			sections = [DocumentSection("Content", ["Empty reviewer"])]

	title = str(data.get("title", path.stem)) if isinstance(data, dict) else path.stem
	parsed = ParsedDocument(title, path.suffix.upper().lstrip("."), sections, source_path=str(path))
	parsed.sync_annotations()
	return parsed


def _parse_pdf_document(path: Path) -> ParsedDocument:
	try:
		from pypdf import PdfReader
	except ImportError as error:
		raise ValueError("PDF support requires the 'pypdf' package.") from error

	reader = PdfReader(str(path))
	page_texts = []
	for page in reader.pages:
		text = (page.extract_text() or "").strip()
		if text:
			page_texts.append(text)

	sections = flatten_pdf_pages_to_document(page_texts)
	parsed = ParsedDocument(path.stem, "PDF", sections, source_path=str(path))
	parsed.sync_annotations()
	return parsed


def _organize_value(value: Any, heading: str = "Content") -> list[DocumentSection]:
	if isinstance(value, dict):
		sections = []
		scalar_lines = []
		for key, child in value.items():
			if isinstance(child, (dict, list)):
				sections.extend(_organize_value(child, str(key)))
			else:
				scalar_lines.append(f"{key}: {child}")
		if scalar_lines:
			sections.insert(0, DocumentSection(heading, scalar_lines))
		return sections or [DocumentSection(heading, ["Empty section"])]

	if isinstance(value, list):
		sections = []
		for index, child in enumerate(value, start=1):
			if isinstance(child, (dict, list)):
				sections.extend(_organize_value(child, f"Item {index}"))
			else:
				sections.append(DocumentSection(heading, [f"{index}. {child}"]))
		return sections or [DocumentSection(heading, ["Empty list"])]

	return [DocumentSection(heading, [str(value)])]


def build_reviewer_payload(document: ParsedDocument) -> dict:
	"""Serialize a document into a reviewer-ready JSON payload."""
	sections = []
	for section in document.sections:
		sections.append({
			"heading": section.heading,
			"content": section.content,
			"notes": section.notes,
			"highlights": sorted(section.highlights),
			"highlight_ranges": {
				line_number: [list(text_range) for text_range in ranges]
				for line_number, ranges in section.highlight_ranges.items()
			},
		})
	return {"title": document.title, "sections": sections}


def save_reviewer(document: ParsedDocument, file_path: str) -> str:
	path = Path(file_path)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(build_reviewer_payload(document), indent=2), encoding="utf-8")
	document.source_path = str(path)
	return str(path)
