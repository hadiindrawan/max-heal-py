import sys
from pathlib import Path

# When testing locally, we want `import max_heal` to point to the `src/` directory.
# Since `src/` is flat and not nested inside `src/max_heal/`, we need to inject it
# directly into the module map so relative internal imports (e.g. `from .config import ...`)
# execute properly.
root = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(root))

# Map the "max_heal" namespace dynamically so tests don't fail when importing it
import importlib.util
spec = importlib.util.spec_from_file_location("max_heal", str(root / "__init__.py"))
if spec and spec.loader:
    module = importlib.util.module_from_spec(spec)
    sys.modules["max_heal"] = module
    spec.loader.exec_module(module)
