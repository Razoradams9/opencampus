"""File storage abstraction.

OpenCampus has no storage provider yet. Content that needs a file is
referenced by an external URL (or written as a text note) until a provider is
added. A provider must implement FileStorage and be returned by
get_file_storage(); until then the API reports file_available = false and
rejects nothing it cannot honour, rather than pretending uploads work.

Rules for a future provider: store opaque keys (never filesystem paths or
bucket URLs) in *storage_key* columns, serve files only through an
authorised endpoint, and scope keys by institution.
"""

from typing import Protocol


class FileStorage(Protocol):
    def open_download(self, key: str) -> bytes: ...

    def save(self, institution_id: str, filename: str, content: bytes) -> str:
        """Store content and return an opaque key."""
        ...


def get_file_storage() -> FileStorage | None:
    """The configured provider, or None (current state: none configured)."""
    return None
