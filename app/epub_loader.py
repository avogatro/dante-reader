"""
EPUB Loader — parses EPUB files using ebooklib.
Extracts spine (chapters), TOC, metadata, cover images, and internal assets.
"""

import os
import re
from typing import Optional
from ebooklib import epub, ITEM_DOCUMENT, ITEM_IMAGE, ITEM_STYLE, ITEM_COVER


class EpubChapter:
    """Represents a single chapter/spine item in an EPUB."""

    __slots__ = ("title", "file_name", "content", "index")

    def __init__(self, title: str, file_name: str, content: bytes, index: int):
        self.title = title
        self.file_name = file_name
        self.content = content  # raw XHTML bytes
        self.index = index

    def get_html(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class EpubBook:
    """High-level wrapper around an ebooklib epub.EpubBook."""

    def __init__(self, epub_path: str):
        self.path = epub_path
        self.filename = os.path.basename(epub_path)
        self._book: Optional[epub.EpubBook] = None
        self.title: str = ""
        self.author: str = ""
        self.language: str = ""
        self.chapters: list[EpubChapter] = []
        self._assets: dict[str, bytes] = {}  # file_name -> raw bytes
        self._asset_types: dict[str, str] = {}  # file_name -> media_type
        self._cover_image: Optional[bytes] = None

        self._load()

    def _load(self) -> None:
        """Parse the EPUB and extract all content."""
        self._book = epub.read_epub(self.path, {"ignore_ncx": False})

        # ── Metadata ──
        self.title = self._get_meta("title") or self._title_from_filename()
        self.author = self._get_meta("creator") or "Unknown Author"
        self.language = self._get_meta("language") or "en"

        # ── Build asset map (CSS, images, fonts) ──
        for item in self._book.get_items():
            name = item.get_name()
            self._assets[name] = item.get_content()
            self._asset_types[name] = item.media_type or "application/octet-stream"

        # ── Extract cover image ──
        self._extract_cover()

        # ── Build spine-ordered chapter list ──
        self._build_chapters()

    def _get_meta(self, key: str) -> str:
        """Safely retrieve a metadata field."""
        try:
            values = self._book.get_metadata("DC", key)
            if values:
                return values[0][0]
        except Exception:
            pass
        return ""

    def _title_from_filename(self) -> str:
        """Derive title from filename if metadata is missing."""
        name = os.path.splitext(self.filename)[0]
        # Strip bracketed Gutenberg ID
        name = re.sub(r"\s*\[\d+\]\s*$", "", name)
        return name

    def _extract_cover(self) -> None:
        """Try to find the cover image from metadata or items."""
        # Method 1: metadata cover reference
        try:
            cover_meta = self._book.get_metadata("OPF", "cover")
            if cover_meta:
                cover_id = cover_meta[0][1].get("content", "")
                if cover_id:
                    for item in self._book.get_items():
                        if item.get_id() == cover_id:
                            self._cover_image = item.get_content()
                            return
        except Exception:
            pass

        # Method 2: items of type ITEM_COVER
        for item in self._book.get_items_of_type(ITEM_COVER):
            self._cover_image = item.get_content()
            return

        # Method 3: look for common cover filenames
        for item in self._book.get_items_of_type(ITEM_IMAGE):
            name_lower = item.get_name().lower()
            if "cover" in name_lower:
                self._cover_image = item.get_content()
                return

    def _build_chapters(self) -> None:
        """Build ordered chapter list from the spine."""
        spine_ids = [item_id for item_id, _ in self._book.spine]
        id_to_item = {}
        for item in self._book.get_items_of_type(ITEM_DOCUMENT):
            id_to_item[item.get_id()] = item

        # Build a TOC label lookup: file_name -> toc_title
        toc_labels = {}
        self._walk_toc(self._book.toc, toc_labels)

        index = 0
        for spine_id in spine_ids:
            item = id_to_item.get(spine_id)
            if item is None:
                continue
            file_name = item.get_name()
            title = toc_labels.get(file_name, f"Chapter {index + 1}")
            self.chapters.append(
                EpubChapter(
                    title=title,
                    file_name=file_name,
                    content=item.get_content(),
                    index=index,
                )
            )
            index += 1

    def _walk_toc(self, toc, labels: dict) -> None:
        """Recursively walk TOC tree and build file_name -> title map."""
        for entry in toc:
            if isinstance(entry, tuple):
                # Nested section: (Section, [children])
                section, children = entry
                if hasattr(section, "href") and hasattr(section, "title"):
                    base_href = section.href.split("#")[0]
                    if section.title:
                        labels[base_href] = section.title
                self._walk_toc(children, labels)
            elif hasattr(entry, "href") and hasattr(entry, "title"):
                base_href = entry.href.split("#")[0]
                if entry.title:
                    labels[base_href] = entry.title

    # ── Public API ──

    def get_chapter(self, index: int) -> Optional[EpubChapter]:
        """Get a chapter by spine index."""
        if 0 <= index < len(self.chapters):
            return self.chapters[index]
        return None

    def get_chapter_count(self) -> int:
        return len(self.chapters)

    def get_cover_image(self) -> Optional[bytes]:
        return self._cover_image

    def get_asset(self, file_name: str) -> Optional[bytes]:
        """Get a raw asset (CSS, image, font) by its internal EPUB path."""
        return self._assets.get(file_name)

    def get_asset_type(self, file_name: str) -> str:
        """Get the MIME type of an asset."""
        return self._asset_types.get(file_name, "application/octet-stream")

    def get_toc_entries(self) -> list[tuple[str, int]]:
        """Return a flat list of (title, chapter_index) for the TOC panel."""
        # Map file_name -> chapter_index for quick lookup
        fname_to_idx = {ch.file_name: ch.index for ch in self.chapters}
        entries = []
        self._flat_toc(self._book.toc, fname_to_idx, entries)

        # If TOC extraction yielded nothing, fall back to spine order
        if not entries:
            for ch in self.chapters:
                entries.append((ch.title, ch.index))
        return entries

    def _flat_toc(self, toc, fname_map: dict, out: list) -> None:
        for entry in toc:
            if isinstance(entry, tuple):
                section, children = entry
                if hasattr(section, "href") and hasattr(section, "title"):
                    base = section.href.split("#")[0]
                    idx = fname_map.get(base)
                    if idx is not None and section.title:
                        out.append((section.title, idx))
                self._flat_toc(children, fname_map, out)
            elif hasattr(entry, "href") and hasattr(entry, "title"):
                base = entry.href.split("#")[0]
                idx = fname_map.get(base)
                if idx is not None and entry.title:
                    out.append((entry.title, idx))
