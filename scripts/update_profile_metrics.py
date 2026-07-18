#!/usr/bin/env python3
"""Update aggregate GitHub profile metrics without exposing repository details."""

from __future__ import annotations

import html
import io
import json
import os
import tarfile
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote


OWNER = os.environ.get("PROFILE_OWNER", "aiwaki")
PROFILE_REPO = os.environ.get("PROFILE_REPO", OWNER)
README = Path("README.md")

METRICS_START = "<!-- profile-metrics:start -->"
METRICS_END = "<!-- profile-metrics:end -->"

EXCLUDED_REPOS = frozenset(
    {
        PROFILE_REPO,
        "gleam-browser-extension",
        *(
            name.strip()
            for name in os.environ.get("PROFILE_EXCLUDED_REPOS", "").split(",")
            if name.strip()
        ),
    }
)

SOURCE_EXTENSIONS = {
    ".bash",
    ".c",
    ".cc",
    ".clj",
    ".cljs",
    ".cpp",
    ".cs",
    ".css",
    ".dart",
    ".erl",
    ".ex",
    ".exs",
    ".fish",
    ".fs",
    ".fsx",
    ".go",
    ".h",
    ".hpp",
    ".hrl",
    ".html",
    ".java",
    ".jl",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".lua",
    ".m",
    ".mm",
    ".mjs",
    ".nim",
    ".php",
    ".pl",
    ".py",
    ".pyw",
    ".r",
    ".rb",
    ".rs",
    ".sass",
    ".scss",
    ".sh",
    ".sql",
    ".svelte",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
    ".zsh",
}

SKIP_DIRS = {
    ".build",
    ".dart_tool",
    ".git",
    ".github",
    ".gradle",
    ".idea",
    ".next",
    ".nuxt",
    ".terraform",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "DerivedData",
    "dist",
    "node_modules",
    "out",
    "Pods",
    "target",
    "vendor",
    "venv",
}

MAX_FILE_BYTES = 1_000_000
LANGUAGE_LIMIT = 7


@dataclass(frozen=True)
class SourceCount:
    lines: int = 0
    files: int = 0


@dataclass(frozen=True)
class ProfileMetrics:
    public_lines: int
    private_lines: int
    public_files: int
    public_repos: int
    language_bytes: dict[str, int]


def request_json(url: str) -> object:
    request = urllib.request.Request(url, headers=request_headers())
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def request_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers=request_headers())
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def request_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "aiwaki-profile-metrics",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def authenticated_owned_repositories() -> list[dict[str, object]]:
    if not os.environ.get("GITHUB_TOKEN"):
        raise RuntimeError("GITHUB_TOKEN with read-only repository access is required")

    viewer = request_json("https://api.github.com/user")
    if not isinstance(viewer, dict) or str(viewer.get("login", "")).casefold() != OWNER.casefold():
        raise RuntimeError(f"GITHUB_TOKEN must authenticate as {OWNER}")

    repos: list[dict[str, object]] = []
    page = 1
    while True:
        batch = request_json(
            "https://api.github.com/user/repos"
            f"?per_page=100&page={page}&affiliation=owner&visibility=all&sort=full_name"
        )
        if not isinstance(batch, list):
            raise RuntimeError("GitHub repositories response was not a list")
        if not batch:
            break
        repos.extend(repo for repo in batch if isinstance(repo, dict))
        page += 1
    return repos


def eligible_repositories(
    repos: list[dict[str, object]],
    excluded_repos: frozenset[str] = EXCLUDED_REPOS,
) -> list[dict[str, object]]:
    eligible: list[dict[str, object]] = []
    for repo in repos:
        owner = repo.get("owner")
        name = str(repo.get("name", ""))
        if not isinstance(owner, dict) or str(owner.get("login", "")) != OWNER:
            continue
        if not name or name in excluded_repos:
            continue
        if repo.get("fork") or repo.get("archived"):
            continue
        eligible.append(repo)
    return sorted(eligible, key=lambda repo: str(repo["name"]).casefold())


def count_repo_lines(repo: dict[str, object]) -> SourceCount:
    name = str(repo["name"])
    branch = str(repo.get("default_branch") or "HEAD")
    encoded_name = quote(name, safe="")
    encoded_branch = quote(branch, safe="")
    archive = request_bytes(
        f"https://api.github.com/repos/{OWNER}/{encoded_name}/tarball/{encoded_branch}"
    )

    files = 0
    lines = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar:
            if not member.isfile() or member.size > MAX_FILE_BYTES:
                continue
            relative = strip_archive_root(member.name)
            if not relative or should_skip(relative):
                continue
            if relative.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            extracted = tar.extractfile(member)
            if not extracted:
                continue
            data = extracted.read()
            if not is_probably_text(data):
                continue
            files += 1
            lines += data.count(b"\n") + int(bool(data) and not data.endswith(b"\n"))
    return SourceCount(lines=lines, files=files)


def repo_language_bytes(repo: dict[str, object]) -> dict[str, int]:
    name = quote(str(repo["name"]), safe="")
    result = request_json(f"https://api.github.com/repos/{OWNER}/{name}/languages")
    if not isinstance(result, dict):
        raise RuntimeError("GitHub languages response was not an object")
    return {
        str(language): int(byte_count)
        for language, byte_count in result.items()
        if isinstance(byte_count, int) and byte_count > 0
    }


def collect_metrics(repos: list[dict[str, object]]) -> ProfileMetrics:
    public_lines = 0
    private_lines = 0
    public_files = 0
    public_repos = 0
    languages: Counter[str] = Counter()

    for repo in repos:
        private = bool(repo.get("private"))
        description = "a private repository" if private else f"public repository {repo['name']}"
        try:
            source = count_repo_lines(repo)
        except (OSError, RuntimeError, tarfile.TarError, urllib.error.URLError, ValueError):
            # Do not put private repository names or request URLs into public action logs.
            raise RuntimeError(f"Unable to inspect {description}; metrics were not changed") from None

        if private:
            private_lines += source.lines
        else:
            try:
                languages.update(repo_language_bytes(repo))
            except (OSError, RuntimeError, urllib.error.URLError, ValueError):
                raise RuntimeError(
                    f"Unable to inspect {description}; metrics were not changed"
                ) from None
            public_lines += source.lines
            public_files += source.files
            public_repos += 1

    return ProfileMetrics(
        public_lines=public_lines,
        private_lines=private_lines,
        public_files=public_files,
        public_repos=public_repos,
        language_bytes=dict(languages),
    )


def strip_archive_root(name: str) -> PurePosixPath | None:
    parts = PurePosixPath(name).parts
    if len(parts) < 2:
        return None
    return PurePosixPath(*parts[1:])


def should_skip(path: PurePosixPath) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def is_probably_text(data: bytes) -> bool:
    if b"\0" in data:
        return False
    if not data:
        return True
    sample = data[:4096]
    control = sum(1 for byte in sample if byte < 9 or 13 < byte < 32)
    return control / len(sample) < 0.08


def approximate_private_lines(lines: int) -> str:
    if lines <= 0:
        return "0"
    rounded = max(1_000, ((lines + 500) // 1_000) * 1_000)
    return f"~{rounded:,}"


def format_language_mix(language_bytes: dict[str, int], limit: int = LANGUAGE_LIMIT) -> str:
    total = sum(byte_count for byte_count in language_bytes.values() if byte_count > 0)
    if total <= 0:
        return "No language data"
    ranked = sorted(
        ((language, byte_count) for language, byte_count in language_bytes.items() if byte_count > 0),
        key=lambda item: (-item[1], item[0].casefold()),
    )
    visible = [
        (language, byte_count)
        for language, byte_count in ranked
        if byte_count / total * 100 >= 0.05
    ][:limit]
    return " · ".join(
        f"{html.escape(language)} {byte_count / total * 100:.1f}"
        for language, byte_count in visible
    )


def render_metrics_block(metrics: ProfileMetrics) -> str:
    return (
        f"{METRICS_START}\n"
        f"  {metrics.public_lines:,} active public source lines · "
        f"{approximate_private_lines(metrics.private_lines)} active private source lines · "
        f"{metrics.public_files:,} public files · {metrics.public_repos} public repos\n"
        "  <br />\n"
        f"  <sub>{format_language_mix(metrics.language_bytes)}</sub>\n"
        f"  {METRICS_END}"
    )


def update_readme(metrics: ProfileMetrics, readme_path: Path = README) -> bool:
    readme = readme_path.read_text(encoding="utf-8")
    before, start, rest = readme.partition(METRICS_START)
    if not start:
        raise RuntimeError(f"{METRICS_START} marker is missing")
    _old, end, after = rest.partition(METRICS_END)
    if not end:
        raise RuntimeError(f"{METRICS_END} marker is missing")

    updated = before + render_metrics_block(metrics) + after
    if updated == readme:
        return False
    readme_path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    repos = eligible_repositories(authenticated_owned_repositories())
    metrics = collect_metrics(repos)
    changed = update_readme(metrics)
    action = "updated" if changed else "verified"
    print(
        f"{action} {metrics.public_lines:,} active public source lines in "
        f"{metrics.public_files:,} files across {metrics.public_repos} public repos; "
        f"{approximate_private_lines(metrics.private_lines)} active private source lines"
    )


if __name__ == "__main__":
    main()
