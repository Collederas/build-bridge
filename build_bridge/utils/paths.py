from pathlib import Path
import sys

from build_bridge.conf import APP_ROOT

def unc_join_path(base_path, unc_path):
    """
    Join a base path with a UNC path using pathlib.
    
    Args:
        base_path (str): The base path
        unc_path (str): The UNC path or any other path to join
        
    Returns:
        str: The joined path with properly handled UNC formatting
    """
    base = Path(base_path)
    
    if unc_path.startswith('//') or unc_path.startswith('\\\\'):
        # Remove the UNC prefix
        unc_path = unc_path[2:]
    
    unc_parts = Path(unc_path).parts
    
    result = base.joinpath(*unc_parts)
    
    # Convert back to string with forward slashes for consistency
    return str(result).replace('\\', '/')


def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller temp folder
        base_path = Path(sys._MEIPASS)
    except Exception:
        # Not bundled, running from source -> use script's directory
        # Assuming this helper is in the same file as SteamUploadDialog
        base_path = Path(APP_ROOT)

    resource_path = base_path / relative_path
    return resource_path