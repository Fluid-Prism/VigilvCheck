"""ui — the desktop interface, kept apart from the checks.

Nothing here decides what a check means, and nothing outside here knows Qt
exists. The CLI and the app run the same registry, which is what keeps
`python3 -m vigilvcheck.audit` honest: it isn't a cut-down version of the
app, it's the same engine with a different surface.
"""
from .window import MainWindow

__all__ = ["MainWindow"]
