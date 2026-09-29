"""
Forward benchmark refresh logs without pipes, reader threads, or unbounded buffering.
"""

import codecs
import os
from collections.abc import Callable
from pathlib import Path

__all__ = ("OperationOutput",)


class OperationOutput:
    """
    Read one operation's durable log from the coordinator and label its terminal output.
    """

    def __init__(self, path: Path, name: str, notify: Callable[[str], None]) -> None:
        """
        Create a fresh log before its worker starts, retaining an independent read offset.

        Args:
            path (Path): Combined stdout and stderr log written by the operation.
            name (str): Operation label attached to forwarded messages.
            notify (Callable[[str], None]): Coordinator's output callback.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
        self.reader = path.open("rb")
        self.name, self.notify = name, notify
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.pending = ""

    def emit(self, text: str, *, final: bool = False) -> None:
        """
        Forward complete lines and split unusually long lines to bound retained memory.

        Args:
            text (str): Newly decoded text; invalid bytes are replaced only on the terminal.
            final (bool): Flush a final line without a newline.

        Returns:
            None: Messages are delivered synchronously by the coordinator.
        """
        self.pending += text.replace("\r", "\n")
        while self.pending:
            newline = self.pending.find("\n", 0, 8192)
            if newline >= 0:
                line, self.pending = self.pending[:newline], self.pending[newline + 1 :]
            elif len(self.pending) >= 8192 or final:
                line, self.pending = self.pending[:8192], self.pending[8192:]
            else:
                break
            if line:
                self.notify(f"[{self.name}] {line}")

    def drain(self, *, final: bool = False) -> None:
        """
        Read bounded batches while running, or the remaining snapshot after completion.

        Args:
            final (bool): Drain the current file length and finalize decoding after the writer stops.

        Returns:
            None: Raw log bytes remain unchanged, including carriage returns and invalid UTF-8.
        """
        remaining = os.fstat(self.reader.fileno()).st_size - self.reader.tell()
        if not final:
            remaining = min(remaining, 65536)
        while remaining > 0:
            chunk = self.reader.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)
            self.emit(self.decoder.decode(chunk))
        if final:
            self.emit(self.decoder.decode(b"", final=True), final=True)

    def close(self) -> None:
        """
        Flush remaining diagnostics and always release the descriptor, even if the sink fails.

        Returns:
            None: The reader is closed after the worker and its descendants have been joined.
        """
        if self.reader.closed:
            return
        try:
            self.drain(final=True)
        finally:
            self.reader.close()
