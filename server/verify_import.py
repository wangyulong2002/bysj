import sys
sys.path.insert(0, ".")
from app.main import app  # noqa: E402

print("APP_IMPORT_OK:", app.title)
