"""
File search module for Shadows File Explorer.

This module provides the FileSearcher class which performs multi-threaded
file searching operations, and the SearchResult class that stores search results.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from utils import is_within

TYPE_EXTENSIONS = {
    'documents': {'.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.rtf', '.md', '.csv'},
    'images': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg', '.ico'},
    'videos': {'.mp4', '.avi', '.mov', '.wmv', '.mkv', '.flv', '.webm'},
    'music': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'},
}


class SearchResult:
    """Represents a single search result.

    Attributes:
        filename: Name of the file
        filepath: Full path to the file
        directory: Directory containing the file
        is_directory: Whether the result is a directory
        size: File size in bytes
        last_modified: Last modified date
        search_id: ID of the search that produced this result
    """

    def __init__(self, filename, filepath, directory, is_dir=False, size=None, mtime=None, search_id=0):
        """Initialize a search result.

        Args:
            filename: Name of the file
            filepath: Full path to the file
            directory: Directory containing the file
            is_dir: Whether the result is a directory
            size: Size in bytes (looked up when omitted)
            mtime: Modification timestamp (looked up when omitted)
            search_id: ID of the search that produced this result
        """
        self.filename = filename
        self.filepath = filepath
        self.directory = directory
        self.is_directory = is_dir
        self.search_id = search_id

        if size is None or mtime is None:
            try:
                stats = os.stat(filepath)
                size, mtime = stats.st_size, stats.st_mtime
            except OSError:
                size, mtime = 0, None

        self.size = size
        self.mtime = mtime
        self.last_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else ""


def passes_filters(name, is_dir, size, mtime, options):
    """Check whether an entry passes the advanced search filters.

    Args:
        name: File or folder name
        is_dir: Whether the entry is a directory
        size: Size in bytes
        mtime: Modification timestamp
        options: Search options dict with optional 'type_filter',
            'size_filter' (min, max) and 'date_filter' ('before'|'after', date)

    Returns:
        bool: True if the entry passes all filters
    """
    type_filter = options.get('type_filter')
    if type_filter and type_filter != 'all':
        if type_filter == 'folders':
            if not is_dir:
                return False
        elif is_dir:
            return False
        elif type_filter in TYPE_EXTENSIONS:
            if os.path.splitext(name)[1].lower() not in TYPE_EXTENSIONS[type_filter]:
                return False

    # Size filter does not apply to directories
    size_filter = options.get('size_filter')
    if size_filter and not is_dir:
        min_size, max_size = size_filter
        if min_size is not None and size < min_size:
            return False
        if max_size is not None and size > max_size:
            return False

    date_filter = options.get('date_filter')
    if date_filter and mtime is not None:
        filter_type, filter_date = date_filter
        file_date = datetime.fromtimestamp(mtime).date()
        if filter_type == 'before' and file_date > filter_date:
            return False
        if filter_type == 'after' and file_date < filter_date:
            return False

    return True


def remove_nested_locations(locations):
    """Drop locations that lie inside another location, so nothing is scanned twice."""
    unique = []
    for location in sorted(set(locations), key=len):
        if not any(is_within(location, kept) for kept in unique):
            unique.append(location)
    return unique


class FileSearcher(QObject):
    """Multi-threaded file search.

    This class provides:
    - Multi-threaded file searching
    - Progress reporting
    - Support for filters (date, size, type)
    - Result streaming

    Every search gets a new search_id. Results and the finished signal carry
    that ID so the UI can ignore anything still arriving from a stopped search.

    Signals:
        started: Emitted when search begins
        finished: Emitted when search completes (search_id)
        progress: Emitted with current progress (scanned, total); total is -1 when unknown
        found_item: Emitted when an item is found (SearchResult)
        status_update: Emitted with status message (str)
    """

    started = pyqtSignal()
    finished = pyqtSignal(int)
    progress = pyqtSignal(int, int)
    found_item = pyqtSignal(object)
    status_update = pyqtSignal(str)

    PROGRESS_INTERVAL = 0.2  # seconds between progress signals

    def __init__(self, parent=None):
        """Initialize the file searcher.

        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        self.search_locations = []
        self.search_term = ""
        self.search_options = {}
        self.search_id = 0
        self.total_files_scanned = 0
        self.result_count = 0

        self.lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._cancel_event.set()
        self._last_progress = 0.0
        self.cpu_count = os.cpu_count() or 4

    @property
    def is_running(self):
        return not self._cancel_event.is_set()

    def configure_search(self, locations, term, options=None):
        """Configure search parameters.

        Args:
            locations: List of directories to search
            term: Search term
            options: Dictionary of search options

        Returns:
            self: For method chaining
        """
        locations = locations if isinstance(locations, list) else [locations]
        self.search_locations = remove_nested_locations(locations)
        self.search_term = term.lower()
        self.search_options = options or {}
        return self

    def start_search(self):
        """Start the search operation, stopping any search still running.

        Returns:
            bool: True if search started successfully
        """
        if not self.search_term or not self.search_locations:
            self.status_update.emit("Nothing to search for")
            return False

        self.stop()

        # Each search gets its own cancel event so stopped workers stay stopped
        self.search_id += 1
        self._cancel_event = threading.Event()
        self.result_count = 0
        self.total_files_scanned = 0

        self.started.emit()

        thread = threading.Thread(
            target=self._run,
            args=(self.search_id, self._cancel_event, list(self.search_locations),
                  self.search_term, dict(self.search_options)),
            daemon=True,
        )
        thread.start()
        return True

    def stop(self):
        """Stop the search operation."""
        if self.is_running:
            self._cancel_event.set()
            self.status_update.emit("Search stopped")

    def _run(self, search_id, cancel, locations, term, options):
        """Coordinate the search: fan top-level folders out to a thread pool."""
        recursive = options.get('include_subfolders', True)
        try:
            self.status_update.emit(f"Searching with {self.cpu_count} threads...")
            with ThreadPoolExecutor(max_workers=self.cpu_count) as pool:
                futures = []
                for location in locations:
                    if cancel.is_set():
                        break
                    if not os.path.isdir(location):
                        self.status_update.emit(f"Location not found: {location}")
                        continue
                    subdirs = self._scan_directory(location, search_id, cancel, term, options)
                    if recursive:
                        futures.extend(
                            pool.submit(self._scan_tree, d, search_id, cancel, term, options)
                            for d in subdirs
                        )
                for future in futures:
                    if cancel.is_set():
                        break
                    future.result()
                if cancel.is_set():
                    pool.shutdown(cancel_futures=True)

            if not cancel.is_set():
                self.status_update.emit(f"Search complete. Found {self.result_count} items.")
        except Exception as e:
            self.status_update.emit(f"Search error: {e}")
        finally:
            cancel.set()
            self.progress.emit(self.total_files_scanned, -1)
            self.finished.emit(search_id)

    def _scan_tree(self, top, search_id, cancel, term, options):
        """Search a directory tree without following symlinked folders."""
        stack = [top]
        while stack and not cancel.is_set():
            stack.extend(self._scan_directory(stack.pop(), search_id, cancel, term, options))

    def _scan_directory(self, directory, search_id, cancel, term, options):
        """Search one directory's entries.

        Returns:
            list: Non-hidden subdirectories to descend into
        """
        subdirs = []
        try:
            with os.scandir(directory) as entries:
                entries = list(entries)
        except OSError:
            return subdirs

        for entry in entries:
            if cancel.is_set():
                break
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if is_dir and not entry.name.startswith('.'):
                subdirs.append(entry.path)
            if term in entry.name.lower():
                self._check_match(entry, is_dir, directory, search_id, options)

        self._report_progress(len(entries))
        return subdirs

    def _check_match(self, entry, is_dir, directory, search_id, options):
        """Apply filters to a name match and emit it as a result."""
        try:
            stats = entry.stat()
            size, mtime = stats.st_size, stats.st_mtime
        except OSError:
            return
        if not passes_filters(entry.name, is_dir, size, mtime, options):
            return
        with self.lock:
            self.result_count += 1
        self.found_item.emit(SearchResult(entry.name, entry.path, directory, is_dir,
                                          size, mtime, search_id))

    def _report_progress(self, scanned):
        """Add to the scanned counter and emit a throttled progress signal."""
        with self.lock:
            self.total_files_scanned += scanned
            now = time.monotonic()
            if now - self._last_progress < self.PROGRESS_INTERVAL:
                return
            self._last_progress = now
            total = self.total_files_scanned
        self.progress.emit(total, -1)
