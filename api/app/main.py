import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path("/opt/sea-speed-api")
DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = BASE_DIR / "media"
OVERLAY_DIR = MEDIA_DIR / "overlays"
EVENTS_MEDIA_DIR = MEDIA_DIR / "events"

STATE_FILE = DATA_DIR / "cam1