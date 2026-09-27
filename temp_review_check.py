from file_handler import ParsedDocument, DocumentSection, save_reviewer, parse_document

d = ParsedDocument("Demo", "PDF", [DocumentSection("Page 1", ["Alpha", "Beta"], {"2": "Check this line"}, {"2"})])
save_reviewer(d, "tmp_reviewer.revx")
x = parse_document("tmp_reviewer.revx")
print(x.title)
print(x.annotations["Page 1"]["2"])
print(sorted(x.highlights["Page 1"]))
