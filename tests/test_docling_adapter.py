import unittest

from src.ingestion.docling_adapter import docling_dict_to_units


class DoclingAdapterTests(unittest.TestCase):
    def test_mapping_preserves_page_bbox_and_table_structure(self):
        exported = {
        "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/tables/0"}]},
        "groups": [],
        "texts": [{
            "self_ref": "#/texts/0", "label": "title", "text": "MX-100",
            "children": [], "prov": [{"page_no": 1, "bbox": {"l": 1, "t": 2, "r": 3, "b": 4}}],
        }],
        "tables": [{
            "self_ref": "#/tables/0", "label": "table", "children": [],
            "prov": [{"page_no": 1, "bbox": {"l": 1, "t": 2, "r": 3, "b": 4}}],
            "data": {"num_rows": 2, "num_cols": 2, "table_cells": [
                {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "代码"},
                {"start_row_offset_idx": 1, "start_col_offset_idx": 0, "text": "E07"},
            ]},
        }],
    }
        units = docling_dict_to_units(exported, "doc_x", "pdf", "sample.pdf")
        self.assertEqual(units[0]["section_path"], ["MX-100"])
        self.assertEqual(units[0]["source_locator"]["page"], 1)
        self.assertEqual(units[1]["structured_data"], [["代码", ""], ["E07", ""]])
        self.assertEqual(units[1]["source_locator"]["bbox"]["l"], 1)

    def test_mapping_is_deterministic(self):
        exported = {
            "body": {"children": [{"$ref": "#/texts/0"}]}, "groups": [], "tables": [],
            "texts": [{"self_ref": "#/texts/0", "label": "text", "text": "stable", "children": [], "prov": []}],
        }
        first = docling_dict_to_units(exported, "doc_x", "docx", "a.docx")
        second = docling_dict_to_units(exported, "doc_x", "docx", "a.docx")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
