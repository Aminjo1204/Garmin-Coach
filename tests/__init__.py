"""Tests laufen in einem leeren Wegwerf-Ordner (COACH_HOME), nie auf den echten Daten.

Start:  .venv\\Scripts\\python.exe -m unittest      (im Projektordner)

Ohne athlete.json im Wegwerf-Ordner gilt athlete.example.json.
"""

import atexit
import os
import shutil
import tempfile

_HOME = tempfile.mkdtemp(prefix="pace-coach-test-")
os.environ["COACH_HOME"] = _HOME
atexit.register(shutil.rmtree, _HOME, ignore_errors=True)
