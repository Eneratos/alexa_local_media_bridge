import os

BRIDGE_VERSION = (
    os.environ.get(
        "BRIDGE_VERSION",
        "development",
    ).strip()
    or "development"
)
