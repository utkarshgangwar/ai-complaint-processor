import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from src.logger import setup_logger

# Load variables from .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"

def load_yaml_config(file_path: Path = CONFIG_PATH) -> dict:
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# Global Configuration Dictionary
CONFIG = load_yaml_config()

# Initialize Logger
LOGGER = setup_logger(
    name=CONFIG.get("app", {}).get("name", "ai_processor"),
    log_dir=str(BASE_DIR / CONFIG.get("paths", {}).get("logs_dir", "logs")),
    level=CONFIG.get("app", {}).get("log_level", "INFO")
)

def ensure_directories() -> None:
    """Dynamically bootstraps input, log, and sub-output directories."""
    paths_cfg = CONFIG.get("paths", {})
    dirs_to_create = [
        BASE_DIR / paths_cfg.get("data_dir", "data"),
        BASE_DIR / paths_cfg.get("logs_dir", "logs"),
        BASE_DIR / paths_cfg.get("structured_data_dir", "output/structured_data"),
        BASE_DIR / paths_cfg.get("customer_emails_dir", "output/customer_emails"),
        BASE_DIR / paths_cfg.get("case_summaries_dir", "output/case_summaries"),
    ]
    for directory in dirs_to_create:
        directory.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Verified application directories.")

# Auto-bootstrap paths upon import
ensure_directories()