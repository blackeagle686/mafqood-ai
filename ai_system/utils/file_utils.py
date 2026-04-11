"""Utility helpers for models and preprocessing."""
import logging
import os
import shutil
import uuid
from typing import Tuple, Optional
from fastapi import UploadFile
import httpx

logger = logging.getLogger(__name__)


def ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def get_file_extension(filename: str) -> str:
    """
    Extract file extension from filename.
    
    Args:
        filename: The filename string
        
    Returns:
        File extension including the dot (e.g., '.jpg')
    """
    return os.path.splitext(filename)[1]


def generate_temp_filename(prefix: str = "", file_extension: str = "") -> str:
    """
    Generate a unique temporary filename.
    
    Args:
        prefix: Optional prefix for the filename
        file_extension: File extension (should include dot, e.g., '.jpg')
        
    Returns:
        Generated filename with UUID
    """
    if prefix and not prefix.endswith("_"):
        prefix += "_"
    return f"{prefix}{uuid.uuid4()}{file_extension}"


def save_uploaded_file(
    file: UploadFile,
    temp_upload_dir: str = "./temp_uploads",
    prefix: str = ""
) -> str:
    """
    Save uploaded file to temp directory.
    
    Args:
        file: UploadFile from FastAPI
        temp_upload_dir: Directory to save temp files
        prefix: Optional prefix for the filename (e.g., 'video', 'search')
        
    Returns:
        Absolute path to the saved file
    """
    os.makedirs(temp_upload_dir, exist_ok=True)
    
    # Get file extension
    ext = get_file_extension(file.filename)
    
    # Generate temp filename
    temp_filename = generate_temp_filename(prefix=prefix, file_extension=ext)
    temp_path = os.path.join(temp_upload_dir, temp_filename)
    
    # Save file
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Return absolute path
    return os.path.abspath(temp_path)


def cleanup_temp_file(file_path: str) -> bool:
    """
    Delete a temporary file.
    
    Args:
        file_path: Path to the file to delete
        
    Returns:
        True if file was deleted, False if it didn't exist
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Cleaned up temp file: {file_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error cleaning up temp file {file_path}: {e}")
        return False


def download_remote_image(url: str, temp_upload_dir: str = "./temp_uploads") -> Optional[str]:
    """
    Download an image from a remote URL to the temp directory.
    
    Args:
        url: The remote URL of the image
        temp_upload_dir: Directory to save the downloaded file
        
    Returns:
        Absolute path to the downloaded file, or None if download failed
    """
    try:
        os.makedirs(temp_upload_dir, exist_ok=True)
        
        # Determine extension from URL or default to .jpg
        ext = os.path.splitext(url.split('?')[0])[1]
        if not ext or len(ext) > 5:
            ext = ".jpg"
            
        from utils.file_utils import generate_temp_filename # Local import to avoid circularity if any
        temp_filename = generate_temp_filename(prefix="remote", file_extension=ext)
        temp_path = os.path.join(temp_upload_dir, temp_filename)
        
        import httpx
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            
            with open(temp_path, "wb") as f:
                f.write(response.content)
                
        logger.info(f"Downloaded remote image from {url} to {temp_path}")
        return os.path.abspath(temp_path)
        
    except Exception as e:
        logger.error(f"Failed to download remote image from {url}: {e}")
        return None
