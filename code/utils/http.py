"""
HTTP request utilities.

This module provides functions for making HTTP requests.
"""

import requests


def download_csv(url: str):
    """
    Download CSV content from a URL.
    
    Args:
        url: URL to download from
    
    Returns:
        CSV content as string
    
    Raises:
        requests.HTTPError: If the request fails
    """
    response = requests.get(url)
    response.raise_for_status()
    return response.text
