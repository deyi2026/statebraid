"""StateBraid runtime package boundary."""

from statebraid.backend import BACKEND_CONTRACT_VERSION
from statebraid.support import SUPPORT_SCOPE_VERSION

__version__ = "0.2.0"
COMPUTE_CONTRACT_VERSION = "0.1"

__all__ = [
    "BACKEND_CONTRACT_VERSION",
    "COMPUTE_CONTRACT_VERSION",
    "SUPPORT_SCOPE_VERSION",
    "__version__",
]
