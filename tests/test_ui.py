import unittest

from applist.ui import get_page_bounds


class PaginationTests(unittest.TestCase):
    def test_page_bounds_clamp_and_slice_filtered_rows(self):
        self.assertEqual(get_page_bounds(0, 3, 500), (0, 0, 0))
        self.assertEqual(get_page_bounds(499, 0, 500), (0, 0, 499))
        self.assertEqual(get_page_bounds(501, 0, 500), (0, 0, 500))
        self.assertEqual(get_page_bounds(501, 1, 500), (1, 500, 501))
        self.assertEqual(get_page_bounds(501, 99, 500), (1, 500, 501))
        self.assertEqual(get_page_bounds(501, -5, 500), (0, 0, 500))


if __name__ == "__main__":
    unittest.main()
