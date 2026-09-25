"""Input adapters.

- url.get_job — single Instagram URL
- file.get_jobs — URL list file (Twos MCP path handoff)
- twos / inbox — REST Twos drain lives on the Workflow 1 branch; inbox still a stub
"""

from adapters.file import get_jobs as get_jobs_from_file
from adapters.job import Job
from adapters.url import get_job

__all__ = ["Job", "get_job", "get_jobs_from_file"]
