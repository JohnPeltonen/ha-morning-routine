import sys
from pathlib import Path

# The package's __init__.py imports homeassistant, so these tests load rules.py and clocks.py on their own.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components" / "morning_routine"))
