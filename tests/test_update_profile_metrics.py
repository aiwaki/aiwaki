from __future__ import annotations

import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from scripts import update_profile_metrics as metrics


def repo(
    name: str,
    *,
    private: bool = False,
    archived: bool = False,
    fork: bool = False,
    owner: str = "aiwaki",
) -> dict[str, object]:
    return {
        "name": name,
        "private": private,
        "archived": archived,
        "fork": fork,
        "default_branch": "main",
        "owner": {"login": owner},
    }


class ProfileMetricsTests(unittest.TestCase):
    def test_repository_filter_excludes_profile_gleam_forks_and_archives(self) -> None:
        repositories = [
            repo("aiwaki"),
            repo("gleam-browser-extension"),
            repo("slipstream"),
            repo("private-work", private=True),
            repo("old", archived=True),
            repo("upstream", fork=True),
            repo("foreign", owner="someone-else"),
        ]

        selected = metrics.eligible_repositories(repositories)

        self.assertEqual([item["name"] for item in selected], ["private-work", "slipstream"])

    def test_private_lines_are_rounded_without_exposing_an_exact_total(self) -> None:
        self.assertEqual(metrics.approximate_private_lines(0), "0")
        self.assertEqual(metrics.approximate_private_lines(499), "~1,000")
        self.assertEqual(metrics.approximate_private_lines(1_499), "~1,000")
        self.assertEqual(metrics.approximate_private_lines(1_500), "~2,000")
        self.assertEqual(metrics.approximate_private_lines(87_654), "~88,000")

    def test_language_mix_is_stable_and_uses_the_full_denominator(self) -> None:
        result = metrics.format_language_mix(
            {"Rust": 2_000, "Python": 7_000, "C++": 1_000, "Tiny": 1, "Ignored": 0},
            limit=3,
        )

        self.assertEqual(result, "Python 70.0 · Rust 20.0 · C++ 10.0")

    def test_private_repositories_do_not_contribute_language_details(self) -> None:
        private_repo = repo("confidential-project", private=True)
        with (
            mock.patch.object(
                metrics,
                "count_repo_lines",
                return_value=metrics.SourceCount(lines=12_345, files=80),
            ),
            mock.patch.object(metrics, "repo_language_bytes") as language_bytes,
        ):
            result = metrics.collect_metrics([private_repo])

        language_bytes.assert_not_called()
        self.assertEqual(result.private_lines, 12_345)
        self.assertEqual(result.language_bytes, {})

    def test_metrics_block_updates_all_values_together(self) -> None:
        profile = metrics.ProfileMetrics(
            public_lines=12_345,
            private_lines=8_765,
            public_files=67,
            public_repos=3,
            language_bytes={"Python": 3, "Rust": 1},
        )
        initial = (
            '<p align="center">\n'
            "  <!-- profile-metrics:start -->old<!-- profile-metrics:end -->\n"
            "</p>\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            readme = Path(directory) / "README.md"
            readme.write_text(initial, encoding="utf-8")

            changed = metrics.update_readme(profile, readme)
            updated = readme.read_text(encoding="utf-8")

        self.assertTrue(changed)
        self.assertIn("12,345 public source lines", updated)
        self.assertIn("~9,000 private source lines", updated)
        self.assertIn("67 public files · 3 public repos", updated)
        self.assertIn("Python 75.0 · Rust 25.0", updated)

    def test_private_repository_failures_do_not_reveal_its_name(self) -> None:
        private_repo = repo("confidential-project", private=True)
        with mock.patch.object(
            metrics,
            "count_repo_lines",
            side_effect=urllib.error.URLError("network down"),
        ):
            with self.assertRaises(RuntimeError) as raised:
                metrics.collect_metrics([private_repo])

        message = str(raised.exception)
        self.assertIn("a private repository", message)
        self.assertNotIn("confidential-project", message)


if __name__ == "__main__":
    unittest.main()
