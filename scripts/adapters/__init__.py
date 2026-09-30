"""Input adapters.

- url.get_job — single Instagram URL
- file.get_jobs — URL list file (Twos MCP path handoff)
- twos.get_jobs / require_jobs — drain Instagram links from a Twos list (REST)
- inbox — still a stub for Shortcut / iCloud drop
"""

from adapters.file import get_jobs as get_jobs_from_file
from adapters.job import Job
from adapters.twos import extract_instagram_urls, get_jobs, require_jobs
from adapters.url import get_job

__all__ = [
    "Job",
    "extract_instagram_urls",
    "get_job",
    "get_jobs",
    "get_jobs_from_file",
    "require_jobs",
]
