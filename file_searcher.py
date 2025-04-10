"""
File search module for Shadows File Explorer.

This module provides the FileSearcher class which performs multi-threaded
file searching operations, and the SearchResult class that stores search results.
"""
import os
import threading
import time
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal


class SearchResult:
    """Represents a single search result.
    
    Attributes:
        filename: Name of the file
        filepath: Full path to the file
        directory: Directory containing the file
        is_directory: Whether the result is a directory
        size: File size in bytes
        last_modified: Last modified date
    """
    
    def __init__(self, filename, filepath, directory, is_dir=False):
        """Initialize a search result.
        
        Args:
            filename: Name of the file
            filepath: Full path to the file
            directory: Directory containing the file
            is_dir: Whether the result is a directory
        """
        self.filename = filename
        self.filepath = filepath
        self.directory = directory
        self.is_directory = is_dir
        self.size = 0
        self.last_modified = ""
        
        try:
            if os.path.exists(filepath):
                stats = os.stat(filepath)
                self.size = stats.st_size
                self.last_modified = datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass


class FileSearcher(QObject):
    """Unified class for file searching operations using all available CPU cores.
    
    This class provides:
    - Multi-threaded file searching
    - Progress reporting
    - Support for filters (date, size, type)
    - Result streaming
    
    Signals:
        started: Emitted when search begins
        finished: Emitted when search completes
        progress: Emitted with current progress (scanned, total)
        found_item: Emitted when an item is found (SearchResult)
        status_update: Emitted with status message (str)
    """
    
    started = pyqtSignal()
    finished = pyqtSignal()
    progress = pyqtSignal(int, int)
    found_item = pyqtSignal(object)
    status_update = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the file searcher.
        
        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        self.search_locations = []
        self.search_term = ""
        self.search_options = {}
        self.is_running = False
        self.abort_requested = False
        self.total_files_scanned = 0
        self.result_count = 0
        
        # For thread management
        self.lock = threading.Lock()
        self.active_threads = []
        
        # Determine optimal thread count (leave one core for UI)
        try:
            import multiprocessing
            self.cpu_count = multiprocessing.cpu_count()
            print(f"Detected {self.cpu_count} CPU cores")
        except (ImportError, NotImplementedError):
            self.cpu_count = 4  # Fallback default
    
    def configure_search(self, locations, term, options=None):
        """Configure search parameters.
        
        Args:
            locations: List of directories to search
            term: Search term
            options: Dictionary of search options
            
        Returns:
            self: For method chaining
        """
        # Make sure locations is a list
        self.search_locations = locations if isinstance(locations, list) else [locations]
        self.search_term = term.lower()
        self.search_options = options or {}
        return self
    
    def start_search(self):
        """Start the search operation.
        
        Returns:
            bool: True if search started successfully
        """
        if not self.search_term or not self.search_locations:
            self.status_update.emit("Nothing to search for")
            return False
            
        # Reset state
        self.is_running = True
        self.abort_requested = False
        self.result_count = 0
        self.total_files_scanned = 0
        
        # Signal that we've started
        self.started.emit()
        
        # Start search thread
        search_thread = threading.Thread(target=self._search_all_locations)
        search_thread.daemon = True
        search_thread.start()
        
        return True
    
    def _search_root_level(self, location):
        """Search just the files in the root level of a directory.
        
        Args:
            location: Directory to search
        """
        try:
            entries = os.listdir(location)
            
            with self.lock:
                self.total_files_scanned += len(entries)
                self.progress.emit(self.total_files_scanned, -1)
            
            for entry in entries:
                if self.abort_requested:
                    return
                
                if os.path.isdir(os.path.join(location, entry)):
                    # Skip directories, they're handled by other threads
                    continue
                
                if self.search_term in entry.lower():
                    full_path = os.path.join(location, entry)
                    if self._passes_filters(full_path, False, 
                                          self.search_options.get('date_filter', None),
                                          self.search_options.get('size_filter', None),
                                          self.search_options.get('type_filter', None)):
                        result = SearchResult(entry, full_path, location, is_dir=False)
                        
                        with self.lock:
                            self.result_count += 1
                        
                        self.found_item.emit(result)
        except Exception as e:
            self.status_update.emit(f"Error searching root level: {str(e)}")
        finally:
            with self.lock:
                current_thread = threading.current_thread()
                if current_thread in self.active_threads:
                    self.active_threads.remove(current_thread)

    def _process_directory_chunk(self, directories):
        """Process a chunk of directories assigned to this thread.
        
        Args:
            directories: List of directories to search
        """
        try:
            for directory in directories:
                if self.abort_requested:
                    return
                
                # Search this directory and all its subdirectories
                for dirpath, dirnames, filenames in os.walk(directory):
                    if self.abort_requested:
                        return
                    
                    # Skip hidden directories
                    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                    
                    with self.lock:
                        self.total_files_scanned += len(filenames) + len(dirnames)
                        if self.total_files_scanned % 100 == 0:
                            self.progress.emit(self.total_files_scanned, -1)
                    
                    # Process directories
                    for dirname in dirnames:
                        if self.abort_requested:
                            return
                        
                        if self.search_term in dirname.lower():
                            full_path = os.path.join(dirpath, dirname)
                            if self._passes_filters(full_path, True, 
                                                 self.search_options.get('date_filter', None), 
                                                 None, 
                                                 self.search_options.get('type_filter', None)):
                                result = SearchResult(dirname, full_path, dirpath, is_dir=True)
                                
                                with self.lock:
                                    self.result_count += 1
                                
                                self.found_item.emit(result)
                    
                    # Process files
                    for filename in filenames:
                        if self.abort_requested:
                            return
                        
                        if self.search_term in filename.lower():
                            full_path = os.path.join(dirpath, filename)
                            if self._passes_filters(full_path, False, 
                                                 self.search_options.get('date_filter', None),
                                                 self.search_options.get('size_filter', None),
                                                 self.search_options.get('type_filter', None)):
                                result = SearchResult(filename, full_path, dirpath, is_dir=False)
                                
                                with self.lock:
                                    self.result_count += 1
                                
                                self.found_item.emit(result)
        except Exception as e:
            self.status_update.emit(f"Error in directory chunk: {str(e)}")
        finally:
            with self.lock:
                current_thread = threading.current_thread()
                if current_thread in self.active_threads:
                    self.active_threads.remove(current_thread)

    def _search_all_locations(self):
        """Search all specified locations using multiple threads."""
        try:
            self.status_update.emit(f"Searching using all {self.cpu_count} CPU cores")
            
            # For each location, create a work queue of subdirectories
            for location in self.search_locations:
                if self.abort_requested:
                    break
                    
                if not os.path.exists(location):
                    self.status_update.emit(f"Location not found: {location}")
                    continue
                
                # First, check if this is a recursive search
                if self.search_options.get('include_subfolders', True):
                    # Create a separate thread for the root level files
                    root_thread = threading.Thread(
                        target=self._search_root_level,
                        args=(location,)
                    )
                    root_thread.daemon = True
                    
                    with self.lock:
                        self.active_threads.append(root_thread)
                    
                    root_thread.start()
                    
                    # Get all top-level subdirectories for distribution
                    try:
                        subdirs = []
                        for entry in os.listdir(location):
                            full_path = os.path.join(location, entry)
                            if os.path.isdir(full_path):
                                subdirs.append(full_path)
                        
                        if subdirs:
                            # Create one worker thread per CPU core
                            worker_count = min(len(subdirs), self.cpu_count - 1)
                            
                            # Distribute directories evenly among workers
                            dir_chunks = self._split_into_chunks(subdirs, worker_count)
                            
                            for chunk in dir_chunks:
                                worker = threading.Thread(
                                    target=self._process_directory_chunk,
                                    args=(chunk,)
                                )
                                worker.daemon = True
                                
                                with self.lock:
                                    self.active_threads.append(worker)
                                
                                worker.start()
                    except (PermissionError, FileNotFoundError):
                        # If we can't list the root directory, fall back to standard method
                        worker = threading.Thread(
                            target=self._search_location,
                            args=(location,)
                        )
                        worker.daemon = True
                        
                        with self.lock:
                            self.active_threads.append(worker)
                        
                        worker.start()
                else:
                    # Non-recursive - just search the location directly
                    worker = threading.Thread(
                        target=self._search_location,
                        args=(location,)
                    )
                    worker.daemon = True
                    
                    with self.lock:
                        self.active_threads.append(worker)
                    
                    worker.start()
            
            # Wait for all threads to complete
            while True:
                with self.lock:
                    if not self.active_threads:
                        break  # All workers done
                
                if self.abort_requested:
                    break  # Search cancelled
                    
                time.sleep(0.1)
                
            self.status_update.emit(f"Search complete. Found {self.result_count} items.")
            
        except Exception as e:
            self.status_update.emit(f"Search error: {str(e)}")
            
        finally:
            self.is_running = False
            self.finished.emit()
    
    def _search_location(self, location):
        """Search a specific location.
        
        Args:
            location: Directory to search
        """
        try:
            include_subfolders = self.search_options.get('include_subfolders', True)
            date_filter = self.search_options.get('date_filter', None)
            size_filter = self.search_options.get('size_filter', None)
            type_filter = self.search_options.get('type_filter', None)
            
            if include_subfolders:
                # Recursive search through subdirectories
                for dirpath, dirnames, filenames in os.walk(location):
                    if self.abort_requested:
                        break
                        
                    # Skip hidden directories
                    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                    
                    with self.lock:
                        self.total_files_scanned += len(filenames) + len(dirnames)
                        if self.total_files_scanned % 100 == 0:
                            self.progress.emit(self.total_files_scanned, -1)
                    
                    # Check directories
                    for dirname in dirnames:
                        if self.abort_requested:
                            return
                            
                        if self.search_term in dirname.lower():
                            full_path = os.path.join(dirpath, dirname)
                            if self._passes_filters(full_path, True, date_filter, None, type_filter):
                                result = SearchResult(dirname, full_path, dirpath, is_dir=True)
                                
                                with self.lock:
                                    self.result_count += 1
                                
                                self.found_item.emit(result)
                    
                    # Check files
                    for filename in filenames:
                        if self.abort_requested:
                            return
                            
                        if self.search_term in filename.lower():
                            full_path = os.path.join(dirpath, filename)
                            if self._passes_filters(full_path, False, date_filter, size_filter, type_filter):
                                result = SearchResult(filename, full_path, dirpath, is_dir=False)
                                
                                with self.lock:
                                    self.result_count += 1
                                
                                self.found_item.emit(result)
            else:
                # Non-recursive search (current directory only)
                try:
                    entries = os.listdir(location)
                    
                    with self.lock:
                        self.total_files_scanned += len(entries)
                        self.progress.emit(self.total_files_scanned, len(entries))
                    
                    for entry in entries:
                        if self.abort_requested:
                            return
                            
                        if self.search_term in entry.lower():
                            full_path = os.path.join(location, entry)
                            is_dir = os.path.isdir(full_path)
                            
                            if self._passes_filters(full_path, is_dir, date_filter, 
                                                   None if is_dir else size_filter, type_filter):
                                result = SearchResult(entry, full_path, location, is_dir=is_dir)
                                
                                with self.lock:
                                    self.result_count += 1
                                
                                self.found_item.emit(result)
                                
                except (PermissionError, FileNotFoundError):
                    self.status_update.emit(f"Cannot access: {location}")
                except Exception as e:
                    self.status_update.emit(f"Error searching: {str(e)}")
        
        finally:
            # Remove this thread from active threads
            with self.lock:
                current_thread = threading.current_thread()
                if current_thread in self.active_threads:
                    self.active_threads.remove(current_thread)
    
    def _passes_filters(self, filepath, is_dir, date_filter=None, size_filter=None, type_filter=None):
        """Check if a file passes all the filters.
        
        Args:
            filepath: Path to check
            is_dir: Whether the path is a directory
            date_filter: Date filter tuple (type, date)
            size_filter: Size filter tuple (min_size, max_size)
            type_filter: Type filter string
            
        Returns:
            bool: True if the file passes all filters
        """
        # Skip if file no longer exists
        if not os.path.exists(filepath):
            return False
            
        # Type filter - directories or specific extensions
        if type_filter and type_filter != 'all':
            if is_dir and type_filter != 'folders':
                return False
            elif not is_dir:
                if type_filter == 'folders':
                    return False
                elif type_filter in ['documents', 'images', 'videos', 'music']:
                    ext = os.path.splitext(filepath)[1].lower()
                    if type_filter == 'documents' and ext not in ['.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
                        return False
                    elif type_filter == 'images' and ext not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                        return False
                    elif type_filter == 'videos' and ext not in ['.mp4', '.avi', '.mov', '.wmv', '.mkv', '.flv']:
                        return False
                    elif type_filter == 'music' and ext not in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma']:
                        return False
        
        # Skip size filter for directories
        if not is_dir and size_filter:
            try:
                size = os.path.getsize(filepath)
                min_size, max_size = size_filter
                
                if min_size is not None and size < min_size:
                    return False
                if max_size is not None and size > max_size:
                    return False
            except:
                pass
                
        # Date filter
        if date_filter:
            try:
                mtime = os.path.getmtime(filepath)
                file_date = datetime.fromtimestamp(mtime).date()
                
                filter_type, filter_date = date_filter
                
                if filter_type == 'before' and file_date > filter_date:
                    return False
                elif filter_type == 'after' and file_date < filter_date:
                    return False
            except:
                pass
                
        return True
    
    def _split_into_chunks(self, items, count):
        """Split a list of items into roughly equal chunks.
        
        Args:
            items: List of items to split
            count: Number of chunks
            
        Returns:
            list: List of chunks
        """
        chunks = []
        chunk_size = max(1, len(items) // count)
        
        for i in range(0, len(items), chunk_size):
            chunks.append(items[i:i + chunk_size])
        
        return chunks

    def stop(self):
        """Stop the search operation."""
        if not self.is_running:
            return
            
        self.abort_requested = True
        self.status_update.emit("Stopping search...")