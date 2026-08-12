import unittest
from types import SimpleNamespace
from unittest import mock

from applist.models import Application
from applist.ui import AppListWindow, FILTER_DEBOUNCE_MS, get_page_bounds, get_source_group_counts


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


class FilterDebounceTests(unittest.TestCase):
    def test_dropdown_changes_share_debounced_filter_refresh(self):
        window = SimpleNamespace()
        callbacks = []
        cancelled = []

        def schedule(delay, callback):
            callbacks.append((delay, callback))
            return f"after-{len(callbacks)}"

        window.after = schedule
        window.after_cancel = cancelled.append
        window._apply_filters = mock.Mock()
        window._cancel_filter_debounce = lambda: AppListWindow._cancel_filter_debounce(window)
        window._schedule_filter_apply = lambda: AppListWindow._schedule_filter_apply(window)
        window._run_debounced_filter_apply = lambda: AppListWindow._run_debounced_filter_apply(window)

        AppListWindow._on_search_changed(window)
        AppListWindow._on_filter_changed(window)

        self.assertEqual(
            [delay for delay, _callback in callbacks],
            [FILTER_DEBOUNCE_MS, FILTER_DEBOUNCE_MS],
        )
        self.assertEqual(cancelled, ["after-1"])

        callbacks[-1][1]()

        window._apply_filters.assert_called_once_with()
        self.assertIsNone(window._filter_debounce_id)


if __name__ == "__main__":
    unittest.main()
