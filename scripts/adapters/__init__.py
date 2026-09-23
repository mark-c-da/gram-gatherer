"""Input adapters.

v1 is a single URL via `url.get_job`. The gather pipeline consumes `Job` only.

Future adapters (do not implement unless asked):
- inbox.py — drain an iCloud/Shortcut inbox file
- twos.py — parse a Twos list export for Instagram URLs
- file.py — read a text file of URLs, one per line
"""

from adapters.job import Job
from adapters.url import get_job

__all__ = ["Job", "get_job"]
