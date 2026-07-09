#!/usr/bin/env python3
"""Update lightweight GitHub profile metrics in README.md."""

from __future__ import annotations

import hashlib
import io
import json
import os
import random
import tarfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


OWNER = os.environ.get("PROFILE_OWNER", "aiwaki")
PROFILE_REPO = os.environ.get("PROFILE_REPO", OWNER)
README = Path("README.md")
BANNER = Path("assets/daily-banner.svg")

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


def update_readme(total_lines: int) -> None:
    readme = README.read_text(encoding="utf-8")
    before, start, rest = readme.partition(START)
    if not start:
        raise RuntimeError(f"{START} marker is missing")
    _old, end, after = rest.partition(END)
    if not end:
        raise RuntimeError(f"{END} marker is missing")

    metric = f"{START}{total_lines:,} public source lines{END}"
    README.write_text(before + metric + after, encoding="utf-8")


def generate_daily_banner() -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    seed = int.from_bytes(hashlib.sha256(f"{OWNER}:{today}".encode()).digest()[:8], "big")
    rng = random.Random(seed)

    width = 1200
    height = 220
    palettes = [
        ("#0b1020", "#13233a", "#8aa4ff", "#64d2ff", "#87f5b5", "#ffd166"),
        ("#10151f", "#1d2836", "#9ccfd8", "#c4a7e7", "#f6c177", "#eb6f92"),
        ("#0c1412", "#183027", "#7ee787", "#58a6ff", "#d2a8ff", "#f2cc60"),
        ("#111016", "#242132", "#a3be8c", "#88c0d0", "#b48ead", "#ebcb8b"),
        ("#0f1218", "#202635", "#7aa2f7", "#9ece6a", "#bb9af7", "#e0af68"),
    ]
    base, deep, accent, cool, warm, spark = rng.choice(palettes)
    cell = rng.choice((18, 20, 24))

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="Daily generated profile banner">'
        ),
        f"<title>daily seed {today}</title>",
        "<defs>",
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">',
        f'<stop offset="0%" stop-color="{base}"/>',
        f'<stop offset="58%" stop-color="{deep}"/>',
        f'<stop offset="100%" stop-color="{base}"/>',
        "</linearGradient>",
        '<radialGradient id="glow" cx="50%" cy="35%" r="70%">',
        f'<stop offset="0%" stop-color="{accent}" stop-opacity="0.26"/>',
        f'<stop offset="55%" stop-color="{cool}" stop-opacity="0.08"/>',
        '<stop offset="100%" stop-color="#000000" stop-opacity="0"/>',
        "</radialGradient>",
        '<filter id="soft"><feGaussianBlur stdDeviation="8"/></filter>',
        '<filter id="tiny"><feGaussianBlur stdDeviation="1.6"/></filter>',
        "</defs>",
        '<rect width="1200" height="220" fill="url(#bg)"/>',
        '<rect width="1200" height="220" fill="url(#glow)"/>',
    ]

    pixel_colors = [accent, cool, warm, spark, "#ffffff"]
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            threshold = 0.16 if y < 120 else 0.30
            if rng.random() > threshold:
                continue
            size = rng.choice((cell, cell, cell * 2))
            opacity = rng.uniform(0.035, 0.16)
            color = rng.choice(pixel_colors)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{size}" height="{cell}" '
                f'fill="{color}" opacity="{opacity:.3f}"/>'
            )

    skyline_y = rng.randint(132, 158)
    for x in range(0, width, rng.choice((22, 24, 28))):
        block_w = rng.randint(18, 54)
        block_h = rng.randint(18, 88)
        color = rng.choice((deep, base, accent, cool))
        parts.append(
            f'<rect x="{x}" y="{skyline_y - block_h}" width="{block_w}" height="{block_h + 90}" '
            f'fill="{color}" opacity="{rng.uniform(0.10, 0.26):.3f}"/>'
        )

    for _ in range(7):
        y = rng.randint(40, 178)
        points = []
        x = -40
        while x <= width + 40:
            points.append(f"{x},{y + rng.randint(-18, 18)}")
            x += rng.randint(85, 150)
        color = rng.choice((accent, cool, warm))
        opacity = rng.uniform(0.18, 0.42)
        parts.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" '
            f'stroke-width="{rng.uniform(1.0, 2.4):.2f}" opacity="{opacity:.3f}" filter="url(#tiny)"/>'
        )

    for _ in range(34):
        x = rng.randint(28, width - 28)
        y = rng.randint(24, height - 30)
        radius = rng.choice((1.4, 1.8, 2.2, 2.8))
        color = rng.choice((accent, cool, warm, spark))
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}" '
            f'opacity="{rng.uniform(0.28, 0.72):.3f}"/>'
        )

    sheen_x = rng.randint(180, 780)
    parts.extend(
        [
            f'<ellipse cx="{sheen_x}" cy="18" rx="260" ry="42" fill="{cool}" opacity="0.07" filter="url(#soft)"/>',
            '<rect x="0" y="0" width="1200" height="220" fill="none" stroke="#ffffff" opacity="0.10"/>',
            (
                f'<text x="1174" y="196" text-anchor="end" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
                f'font-size="11" fill="#ffffff" opacity="0.22">seed {today.replace("-", ".")}</text>'
            ),
            "</svg>",
        ]
    )

    BANNER.parent.mkdir(parents=True, exist_ok=True)
    BANNER.write_text("\n".join(parts) + "\n", encoding="utf-8")


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

    update_readme(total_lines)
    generate_daily_banner()
    print(f"counted {total_lines:,} source lines in {total_files:,} files across {len(repos)} repos")


if __name__ == "__main__":
    main()
