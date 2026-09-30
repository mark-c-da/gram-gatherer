"""Input adapters.

- url.get_job — single Instagram URL
- file.get_jobs — URL list file (Twos MCP path handoff)
- twos.get_jobs / require_jobs — drain Instagram links from a Twos list (REST)
- inbox.get_jobs — Shortcut / iCloud ``inbox.txt`` drop
"""

from adapters.file import get_jobs as get_jobs_from_file
from adapters.inbox import default_inbox_path, get_jobs as get_jobs_from_inbox, resolve_inbox_path
from adapters.job import Job
from adapters.twos import extract_instagram_urls, get_jobs, require_jobs
from adapters.url import get_job

__all__ = [
    "Job",
    "default_inbox_path",
    "extract_instagram_urls",
    "get_job",
    "get_jobs",
    "get_jobs_from_file",
    "get_jobs_from_inbox",
    "require_jobs",
    "resolve_inbox_path",
]
