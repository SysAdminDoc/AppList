import unittest

from applist.models import Application
from applist.ui import get_page_bounds, get_source_group_counts


class PaginationTests(unittest.TestCase):
    def test_page_bounds_clamp_and_slice_filtered_rows(self):
        self.assertEqual(get_page_bounds(0, 3, 500), (0, 0, 0))
        self.assertEqual(get_page_bounds(499, 0, 500), (0, 0, 499))
        self.assertEqual(get_page_bounds(501, 0, 500), (0, 0, 500))
        self.assertEqual(get_page_bounds(501, 1, 500), (1, 500, 501))
        self.assertEqual(get_page_bounds(501, 99, 500), (1, 500, 501))
        self.assertEqual(get_page_bounds(501, -5, 500), (0, 0, 500))

    def test_source_group_counts_use_unknown_fallback(self):
        counts = get_source_group_counts(
            [
                Application(name="Alpha", source="HKLM64"),
                Application(name="Beta", source="HKLM64"),
                Application(name="Gamma", source=""),
            ]
        )

        self.assertEqual(counts, {"HKLM64": 2, "Unknown": 1})


if __name__ == "__main__":
    unittest.main()
