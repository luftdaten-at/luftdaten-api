"""
General helper utilities.

This module contains general-purpose helper functions.
"""


def float_default(x, default=None):
    """
    Try to convert x to float, return default if conversion fails.
    
    Args:
        x: Value to convert to float
        default: Default value to return if conversion fails (default: None)
    
    Returns:
        float value if conversion succeeds, otherwise default value
    """
    try:
        return float(x)
    except (ValueError, TypeError):
        return default
