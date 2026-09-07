import json
import time
from pathlib import Path
from typing import Any, Dict
from src.config import LOGGER

def save_text_file(content: str, destination_path: Path) -> None:
    """Safely writes UTF-8 text content to a destination path."""
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with open(destination_path, "w", encoding="utf-8") as f:
        f.write(content)
    LOGGER.debug(f"Saved text artifact: {destination_path.name}")

def save_json_file(data: Dict[str, Any], destination_path: Path) -> None:
    """Safely writes formatted JSON data to a destination path."""
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with open(destination_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    LOGGER.debug(f"Saved JSON artifact: {destination_path.name}")

def get_base_filename(file_path: str | Path) -> str:
    """Returns the stem (filename without extension) cleanly."""
    return Path(file_path).stem