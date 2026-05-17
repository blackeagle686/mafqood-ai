import os
from typing import Union

import requests


def download_image(url: str, dest_folder: Union[str, os.PathLike]) -> str:
    """Download an image from ``url`` and save it into ``dest_folder``.

    Returns the full path to the written file.  If ``dest_folder`` does not
    exist it will be created.  The filename is taken from the last path
    component of the URL (query string removed).
    """
    os.makedirs(dest_folder, exist_ok=True)

    response = requests.get(url, stream=True)
    response.raise_for_status()

    filename = os.path.basename(url.split("?")[0])
    if not filename:
        filename = "image"
    path = os.path.join(dest_folder, filename)

    with open(path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return path
