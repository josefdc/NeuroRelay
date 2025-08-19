from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("neurorelay")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable dev
