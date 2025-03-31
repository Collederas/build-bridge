from pathlib import Path

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
    
    # Split the unc_path into parts to handle properly
    unc_parts = Path(unc_path).parts
    
    # Join the paths
    result = base.joinpath(*unc_parts)
    
    # Convert back to string with forward slashes for consistency
    return str(result).replace('\\', '/')