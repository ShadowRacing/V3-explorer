"""
File operation safety module for Shadows File Explorer.

This module provides the FileOperationSafetyManager class which ensures secure file operations
by identifying protected system locations, checking permissions, and handling recycle bin operations.
"""
import os
import platform
import ctypes
from ctypes import windll, wintypes
import time


class _SHFILEOPSTRUCTW(ctypes.Structure):
    """Windows API structure for shell file operations (needed for recycle bin)."""
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR)
    ]


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
        self.shell32 = ctypes.windll.shell32 if platform.system() == "Windows" else None
        self.protected_locations = self._get_protected_locations()
        self.dangerous_extensions = ['.exe', '.bat', '.cmd', '.vbs', '.js', '.msi', '.ps1', '.reg', '.scr', '.hta']
        
    def _get_protected_locations(self):
        """Get list of protected system locations.
        
        Returns:
            list: Paths to protected system locations
        """
        locations = []
        if platform.system() == "Windows":
            # Add common protected Windows folders
            for var in ['SystemRoot', 'ProgramFiles', 'ProgramFiles(x86)', 'ProgramData']:
                path = os.environ.get(var)
                if path:
                    locations.append(path)
            
            # Add System32 and other critical folders
            system_root = os.environ.get('SystemRoot', 'C:\\Windows')
            locations.append(os.path.join(system_root, 'System32'))
            locations.append(os.path.join(system_root, 'SysWOW64'))
            locations.append(os.path.join(os.environ.get('SystemDrive', 'C:'), 'System Volume Information'))
            locations.append(os.path.join(os.environ.get('SystemDrive', 'C:'), '$Recycle.Bin'))
        else:
            # For non-Windows systems, add Unix system directories
            locations.extend(['/bin', '/usr/bin', '/sbin', '/usr/sbin', '/etc', '/var'])
            
        return locations
    
    def is_location_protected(self, path):
        """Check if a location is protected and should show warning.
        
        Args:
            path: Path to check
            
        Returns:
            bool: True if location is protected
        """
        for protected in self.protected_locations:
            if os.path.normpath(path).startswith(os.path.normpath(protected)):
                return True
        return False
    
    def is_file_from_internet(self, path):
        """Check if a file has the 'downloaded from internet' flag.
        
        Args:
            path: Path to check
            
        Returns:
            bool: True if file was downloaded from internet
        """
        if platform.system() != "Windows":
            return False
            
        try:
            # Check NTFS Zone Identifier stream
            zone_path = path + ":Zone.Identifier"
            return os.path.exists(zone_path)
        except:
            # Fallback: check if in Downloads folder
            downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            return os.path.normpath(os.path.dirname(path)).startswith(os.path.normpath(downloads))
    
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
            
        try:
            # Try to create a temporary file to check write access
            if os.path.isdir(path):
                test_path = os.path.join(path, f".test_{int(time.time())}")
                with open(test_path, 'w') as f:
                    pass
                os.remove(test_path)
            else:
                # For files, check parent directory
                parent_dir = os.path.dirname(path)
                test_path = os.path.join(parent_dir, f".test_{int(time.time())}")
                with open(test_path, 'w') as f:
                    pass
                os.remove(test_path)
            return False
        except (PermissionError, OSError):
            return True
    
    def move_to_recycle_bin(self, paths):
        """Move files/folders to recycle bin instead of permanent deletion.
        
        Args:
            paths: Single path or list of paths to move to recycle bin
            
        Returns:
            bool: True if operation successful
        """
        if platform.system() != "Windows" or not self.shell32:
            return False
            
        if isinstance(paths, str):
            paths = [paths]
            
        # Convert to required format for Windows API
        file_op_flags = 0x0040  # FOF_ALLOWUNDO flag for recycle bin
        if not self.parent:
            file_op_flags |= 0x0010  # FOF_SILENT
            
        for path in paths:
            try:
                path_buf = ctypes.create_unicode_buffer(path)
                result = self.shell32.SHFileOperationW(ctypes.byref(
                    _SHFILEOPSTRUCTW(
                        hwnd=0, 
                        wFunc=0x0003,  # FO_DELETE
                        pFrom=path_buf,
                        pTo=None,
                        fFlags=file_op_flags
                    )
                ))
                if result != 0:
                    return False
            except:
                return False
        return True
    
    def check_delete_safety(self, paths):
        """Check if it's safe to delete these paths.
        
        Args:
            paths: List of paths to check
            
        Returns:
            tuple: (is_safe, message) - Bool indicating safety and message if unsafe
        """
        if not paths:
            return True, None
            
        protected_paths = [p for p in paths if self.is_location_protected(p)]
        admin_paths = [p for p in paths if self.requires_admin_privileges(p)]
        
        if protected_paths:
            return False, "You're attempting to delete files from protected system folders. This could harm your system."
            
        if admin_paths:
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
