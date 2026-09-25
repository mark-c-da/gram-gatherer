"""Input adapters.

- url.get_job — single Instagram URL (v1)
- twos.get_jobs / require_jobs — drain Instagram links from a Twos list (Workflow 1)
- inbox / file — still stubs for later shells
"""

from adapters.job import Job
from adapters.twos import extract_instagram_urls, get_jobs, require_jobs
from adapters.url import get_job

__all__ = [
    "Job",
    "extract_instagram_urls",
    "get_job",
    "get_jobs",
    "require_jobs",
]
