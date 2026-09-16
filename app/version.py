from pathlib import Path


def read_version() -> str:
    for path in (
        Path(__file__).resolve().parent.parent / "VERSION",
        Path("/app/VERSION"),
    ):
        try:
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            pass

    return "dev"


APP_VERSION = read_version()
