"""Shallow-clone connector grounding repos for the agentic resolver.

Each connector with `source_repo_url` set gets cloned once to a local
directory. The agentic LLM's filesystem tools (`list_directory`,
`read_file`, `search_files`) operate against that clone. Network-bound
git work happens at connector save time, not at resolve time.
"""

from __future__ import annotations

import ipaddress
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


class GroundingCloneError(Exception):
    """Raised when a clone cannot complete safely."""


def _validate_url(url: str) -> None:
    """Reject URLs that could SSRF or escape sandbox before invoking git."""
    if url.startswith("file://"):
        return  # for local tests; production callers should not pass file://
    if not url.startswith("https://"):
        raise GroundingCloneError(f"only https:// (or file://) URLs allowed: {url!r}")
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise GroundingCloneError(f"missing hostname: {url!r}")
    if hostname in {"localhost", "ip6-localhost", "ip6-loopback"}:
        raise GroundingCloneError(f"localhost not allowed: {url!r}")
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return  # hostname, not an IP literal -- allowed
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        raise GroundingCloneError(f"private/local IP not allowed: {url!r}")


def clone_repo(*, url: str, target: Path, revision: str = "main") -> str:
    """Shallow-clone `url` at `revision` into `target`. Return the HEAD SHA."""
    _validate_url(url)
    if target.exists():
        raise GroundingCloneError(f"target already exists: {target}")
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        revision,
        url,
        str(target),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace")
        raise GroundingCloneError(f"git clone failed: {stderr.strip()}") from exc

    sha_proc = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return sha_proc.stdout.strip()


def delete_clone(target: Path) -> None:
    """Remove a previously-cloned repo directory. No-op if missing."""
    if not target.exists():
        return
    shutil.rmtree(target)
