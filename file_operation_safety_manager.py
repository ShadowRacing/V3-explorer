"""
File operation safety module for Shadows File Explorer.

This module provides the FileOperationSafetyManager class which ensures secure file operations
by identifying protected system locations, checking permissions, and handling recycle bin operations.
"""
import os
import tempfile

from PyQt6.QtCore import QFile

from utils import IS_WINDOWS, is_within


class FileOperationSafetyManager:
    """Manages security and safety aspects of file operations.

    This class provides methods to:
    - Identify protected system locations
    - Check file permissions
    - Verify if operations require admin privileges
    - Handle recycle bin operations
    - Protect against dangerous operations
    """

    def __init__(self, parent=None):
        """Initialize the safety manager.

        Args:
            parent: Parent widget (optional)
        """
        self.parent = parent
        self.protected_locations = self._get_protected_locations()
        self.dangerous_extensions = ['.exe', '.bat', '.cmd', '.vbs', '.js', '.msi', '.ps1', '.reg', '.scr', '.hta',
                                     '.com', '.pif', '.jar', '.lnk', '.sh']

    def _get_protected_locations(self):
        """Get list of protected system locations.

        Returns:
            list: Paths to protected system locations
        """
        locations = []
        if IS_WINDOWS:
            # Add common protected Windows folders
            for var in ['SystemRoot', 'ProgramFiles', 'ProgramFiles(x86)', 'ProgramData']:
                path = os.environ.get(var)
                if path:
                    locations.append(path)

            # Add System32 and other critical folders
            system_root = os.environ.get('SystemRoot', 'C:\\Windows')
            system_drive = os.environ.get('SystemDrive', 'C:') + "\\"
            locations.append(os.path.join(system_root, 'System32'))
            locations.append(os.path.join(system_root, 'SysWOW64'))
            locations.append(os.path.join(system_drive, 'System Volume Information'))
            locations.append(os.path.join(system_drive, '$Recycle.Bin'))
        else:
            # For non-Windows systems, add Unix system directories
            locations.extend(['/bin', '/usr/bin', '/sbin', '/usr/sbin', '/etc', '/var', '/boot',
                              '/System', '/Library'])

        return locations

    def is_location_protected(self, path):
        """Check if a location is protected and should show warning.

        Args:
            path: Path to check

        Returns:
            bool: True if location is protected
        """
        return any(is_within(path, protected) for protected in self.protected_locations)

    def is_file_from_internet(self, path):
        """Check if a file has the 'downloaded from internet' flag.

        Args:
            path: Path to check

        Returns:
            bool: True if file was downloaded from internet
        """
        if not IS_WINDOWS:
            return False

        try:
            # Check NTFS Zone Identifier stream
            return os.path.exists(path + ":Zone.Identifier")
        except OSError:
            # Fallback: check if in Downloads folder
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            return is_within(path, downloads)

    def is_executable_file(self, path):
        """Check if file is a potentially dangerous executable type.

        Args:
            path: Path to check

        Returns:
            bool: True if file is executable
        """
        ext = os.path.splitext(path)[1].lower()
        return ext in self.dangerous_extensions

    def requires_admin_privileges(self, path):
        """Check if operation requires admin rights.

        Args:
            path: Path to check

        Returns:
            bool: True if admin rights are required
        """
        if not os.path.exists(path):
            return False

        directory = path if os.path.isdir(path) else os.path.dirname(path)
        if not IS_WINDOWS:
            return not os.access(directory, os.W_OK)

        # os.access ignores ACLs on Windows, so actually try to write
        try:
            with tempfile.TemporaryFile(dir=directory):
                pass
            return False
        except OSError:
            return True

    def move_to_recycle_bin(self, paths):
        """Move files/folders to the recycle bin (trash) instead of permanent deletion.

        Args:
            paths: Single path or list of paths to move to recycle bin

        Returns:
            list: Paths that could NOT be moved to the recycle bin
        """
        if isinstance(paths, str):
            paths = [paths]

        failed = []
        for path in paths:
            # QFile.moveToTrash works on Windows, macOS and freedesktop Linux
            # PyQt6 returns (success, path_in_trash)
            success, _ = QFile.moveToTrash(path)
            if not success:
                failed.append(path)
        return failed

    def check_delete_safety(self, paths):
        """Check if it's safe to delete these paths.

        Args:
            paths: List of paths to check

        Returns:
            tuple: (is_safe, message) - Bool indicating safety and message if unsafe
        """
        if not paths:
            return True, None

        if any(self.is_location_protected(p) for p in paths):
            return False, "You're attempting to delete files from protected system folders. This could harm your system."

        if any(self.requires_admin_privileges(p) for p in paths):
            return False, "This operation requires administrator privileges."

        return True, None

    def check_file_open_safety(self, path):
        """Check if a file is safe to open.

        Args:
            path: Path to check

        Returns:
            tuple: (is_safe, message) - Bool indicating safety and message if unsafe
        """
        if not os.path.exists(path) or os.path.isdir(path):
            return True, None

        if self.is_file_from_internet(path):
            return False, "This file was downloaded from the Internet and may be unsafe. Do you want to open it anyway?"

        if self.is_executable_file(path):
            return False, "This file is an executable and could potentially harm your computer. Are you sure you want to run it?"

        return True, None
