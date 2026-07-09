#!/usr/bin/env python3
"""Update lightweight GitHub profile metrics in README.md."""

from __future__ import annotations

import io
import json
import os
import tarfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath


OWNER = os.environ.get("PROFILE_OWNER", "aiwaki")
PROFILE_REPO = os.environ.get("PROFILE_REPO", OWNER)
README = Path("README.md")

START = "<!-- code-lines:start -->"
END = "<!-- code-lines:end -->"

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


def public_source_repos() -> list[dict[str, object]]:
    repos: list[dict[str, object]] = []
    page = 1
    while True:
        batch = request_json(
            f"https://api.github.com/users/{OWNER}/repos"
            f"?per_page=100&page={page}&type=owner&sort=full_name"
        )
        if not isinstance(batch, list):
            raise RuntimeError("GitHub repos response was not a list")
        if not batch:
            break
        repos.extend(
            repo
            for repo in batch
            if repo.get("owner", {}).get("login") == OWNER
            and not repo.get("fork")
            and not repo.get("archived")
            and not repo.get("private")
            and repo.get("name") != PROFILE_REPO
        )
        page += 1
    return repos


def count_repo_lines(repo: dict[str, object]) -> tuple[int, int]:
    name = str(repo["name"])
    branch = str(repo.get("default_branch") or "HEAD")
    archive = request_bytes(f"https://api.github.com/repos/{OWNER}/{name}/tarball/{branch}")

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
    return lines, files


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


def update_readme(total_lines: int, total_files: int, repo_count: int) -> None:
    readme = README.read_text(encoding="utf-8")
    before, start, rest = readme.partition(START)
    if not start:
        raise RuntimeError(f"{START} marker is missing")
    _old, end, after = rest.partition(END)
    if not end:
        raise RuntimeError(f"{END} marker is missing")

    metric = f"{START}{total_lines:,} public source lines · {total_files:,} files · {repo_count} repos{END}"
    README.write_text(before + metric + after, encoding="utf-8")


def main() -> None:
    repos = public_source_repos()
    total_lines = 0
    total_files = 0
    for repo in repos:
        try:
            lines, files = count_repo_lines(repo)
        except (urllib.error.URLError, tarfile.TarError) as error:
            print(f"warning: skipped {repo['name']}: {error}")
            continue
        total_lines += lines
        total_files += files

    update_readme(total_lines, total_files, len(repos))
    print(f"counted {total_lines:,} source lines in {total_files:,} files across {len(repos)} repos")


if __name__ == "__main__":
    main()
