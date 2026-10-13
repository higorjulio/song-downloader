import threading
from pathlib import Path

#delete file after...
FILE_TTL_SECONDS = 10 * 60


def delete_file_later(file_path: Path | str, delay_seconds: int = FILE_TTL_SECONDS) -> None:

    file_path = Path(file_path)

    def _delete():
        if file_path.exists():
            file_path.unlink()

    timer = threading.Timer(delay_seconds, _delete)
    timer.daemon = True
    timer.start()