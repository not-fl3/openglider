from __future__ import annotations

import itertools
import logging
from typing import TYPE_CHECKING, Any

import openglider
from openglider.gui.qt import QtCore, QtWidgets
from qasync import QEventLoop
from qtconsole.inprocess import (QtInProcessKernelClient,
                                  QtInProcessKernelManager)
from qtconsole.rich_jupyter_widget import RichJupyterWidget

if TYPE_CHECKING:
    from openglider.gui.app.main_window import MainWindow

import asyncio

logging.getLogger("openglider")


class OpenGliderKernel(QtInProcessKernelClient):
    loop: QEventLoop = None

    def _dispatch_to_kernel(self, msg: str) -> None:
        """Send a message to the kernel and handle a reply."""
        kernel = self.kernel
        if kernel is None:
            raise RuntimeError("Cannot send request. No kernel exists.")

        stream = kernel.shell_stream
        self.session.send(stream, msg)
        msg_parts = stream.recv_multipart()

        asyncio.ensure_future(self.async_dispatch(msg_parts))
    
    async def async_dispatch(self, msg_parts: list[str]) -> None:
        await self.kernel.dispatch_shell(msg_parts)
        idents, reply_msg = self.session.recv(self.kernel.shell_stream, copy=False)
        self.shell_channel.call_handlers_later(reply_msg)

class OpenGliderKernelManager(QtInProcessKernelManager):
    client_class = "openglider.gui.views.console.OpenGliderKernel"

class ConsoleWidget(RichJupyterWidget):
    """
    Convenience class for a live IPython console widget.
    We can replace the standard banner using the customBanner argument
    """

    # ANSI colors used for the plain-text "In [n]:" / "Out[n]:" prompts we
    # reconstruct when replaying buffered user input/output (see
    # ``_record_io_text`` below). Chosen to match the colors used by
    # qtconsole's own "linux"/dark style sheet for the live HTML prompts
    # (green for input, red for output).
    IN_PROMPT_COLOR = "\x1b[92m"   # bright green
    OUT_PROMPT_COLOR = "\x1b[91m"  # bright red
    IO_RESET = "\x1b[0m"

    def __init__(self, app: MainWindow, customBanner: Any=None, *args: Any, **kwargs: Any):

        super().__init__(*args, **kwargs)
        self.app = app
        self.kernel_manager = OpenGliderKernelManager()
        self.kernel_manager.start_kernel()

        self.kernel_manager.kernel.gui = 'qt'
        self.kernel_client = kernel_client = self.kernel_manager.client()
        kernel_client.loop = app.app.loop
        #kernel_client.start_channels(shell=False, iopub=False, stdin=False, hb=False)
        kernel_client.start_channels()

        self.set_default_style("linux")
        self.font_size = 6
        self.gui_completion = 'droplist'

        # ansi color codes (used for log-level coloring) need to be enabled
        self.ansi_codes = True

        # whether user input (executed code) / output (results, stdout,
        # stderr, display data) should currently be shown. Controlled by
        # the "User Input/Output" checkbox in the LogFilterPanel.
        self.io_visible = True

        # every log-message (via ConsoleHandler) and every bit of user
        # input/output shares a single monotonically increasing sequence
        # counter, so that the two kinds of content can be interleaved in
        # the correct chronological order whenever the console needs to be
        # fully re-rendered (e.g. because a filter changed).
        self._seq_counter = itertools.count()

        # plain-text reconstruction of everything that went through the
        # in/out/stream/error/display handlers below, so it can be
        # re-rendered later regardless of the current io_visible state.
        # Every stored entry already has consistent trailing newlines, so
        # replaying them back-to-back produces correctly separated blocks.
        self._io_records: list[tuple[int, str]] = []

        self.push_local_ns("app", self.app)
        self.push_local_ns("openglider", openglider)

    def next_seq(self) -> int:
        """
        Returns the next value of the shared log/io sequence counter.
        """
        return next(self._seq_counter)

    def _record_io_text(self, text: str) -> None:
        """
        Stores a piece of user input/output for later replay, normalizing
        trailing newlines so re-rendered blocks don't run into each other
        or accumulate extra blank lines.
        """
        if not text:
            return

        if not text.endswith("\n"):
            text += "\n"

        seq = self.next_seq()
        self._io_records.append((seq, text))

    # -- overrides that capture user input/output for later replay --------
    #
    # Each of these mirrors the corresponding qtconsole/jupyter_widget
    # handler: we build a plain-text approximation of what is being shown
    # (good enough for re-display purposes) and store it, then - if
    # io_visible is currently enabled - let the original handler run so the
    # normal, nicely formatted output still appears live exactly as before.

    def _handle_execute_input(self, msg: Any) -> None:
        content = msg.get('content', {})
        code = content.get('code', '')
        number = content.get('execution_count', 0)
        lines = code.split('\n')

        in_prompt = f"{self.IN_PROMPT_COLOR}In [{number}]:{self.IO_RESET}"
        text_lines = [f"{in_prompt} {lines[0] if lines else ''}"]
        for line in lines[1:]:
            text_lines.append(f"   ...: {line}")

        # a leading blank line visually separates this input block from
        # whatever was printed right before it (matches qtconsole's own
        # spacing before a new prompt).
        self._record_io_text("\n" + "\n".join(text_lines) + "\n")

        if self.io_visible:
            super()._handle_execute_input(msg)

    def _handle_execute_result(self, msg: Any) -> None:
        content = msg.get('content', {})
        number = content.get('execution_count', 0)
        data = content.get('data', {})
        text_plain = data.get('text/plain', '')
        out_prompt = f"{self.OUT_PROMPT_COLOR}Out[{number}]:{self.IO_RESET}"
        self._record_io_text(f"{out_prompt} {text_plain}")

        if self.io_visible:
            super()._handle_execute_result(msg)

    def _handle_display_data(self, msg: Any) -> None:
        data = msg.get('content', {}).get('data', {})
        text_plain = data.get('text/plain', '')
        if text_plain:
            self._record_io_text(text_plain)

        if self.io_visible:
            super()._handle_display_data(msg)

    def _handle_error(self, msg: Any) -> None:
        content = msg.get('content', {})
        traceback = '\n'.join(content.get('traceback', []))
        if traceback:
            self._record_io_text(traceback)

        if self.io_visible:
            super()._handle_error(msg)

    def _handle_stream(self, msg: Any) -> None:
        text = msg.get('content', {}).get('text', '')
        self._record_io_text(text)

        if self.io_visible:
            super()._handle_stream(msg)

    def set_io_visible(self, visible: bool) -> None:
        """
        Enables/disables live display of user input/output. Does not by
        itself trigger a re-render of already-shown content - see
        ``ConsoleHandler.refresh`` for that.
        """
        self.io_visible = visible

    def replay_io_text(self, text: str) -> None:
        """
        Re-displays a previously captured piece of user input/output text
        (used when re-rendering the console after a filter change). The
        text already carries its own trailing newline (see
        ``_record_io_text``), so it is written verbatim.
        """
        self.append_stream(text)
        self._scroll_to_end()

    def _complete(self) -> None:
        code = self.input_buffer

        # TODO: check what happens on autocompletion
        if code.startswith("app"):
            cursor_pos = self._get_input_buffer_cursor_pos()
            msg_id = self.kernel_client.complete(code=code, cursor_pos=cursor_pos)
            info = self._CompletionRequest(msg_id, code, cursor_pos)
            self._request_info['complete'] = info

            print(msg_id)
            return
        return super()._complete()

    def push_local_ns(self, name: str, value: Any) -> None:
        """
        Given a dictionary containing name / value pairs, push those variables
        to the IPython console widget
        """
        if self.kernel_manager.kernel is not None:
            self.kernel_manager.kernel.shell.push({name: value})

    def clear(self) -> None:
        """
        Clears the terminal
        """
        self._control.clear()

        # clearing the underlying text widget wipes the input prompt too
        # (it is not redrawn automatically), so ask for a fresh one to be
        # shown again, otherwise the prompt disappears after a refresh.
        self._show_interpreter_prompt()

        # self.kernel_manager

    def print_text(self, text: str) -> None:
        """
        Prints some plain text to the console
        """
        self.append_stream(text)
        self._scroll_to_end()
        #self._append_plain_text(text)

    def execute_command(self, command: str) -> None:
        """
        Execute a command in the frame of the console widget
        """
        self._execute(command, False)
    
    def log_message(self, message: str) -> None:
        self.print_text(message + '\n')


class QSignaler(QtCore.QObject):
    log_message = QtCore.Signal(int, str)


class LogFilterPanel(QtWidgets.QWidget):
    """
    Small side-panel (meant to be placed left of the console) that lets the
    user filter the log output shown in the console:

      - a single choice of the minimum log-level to display (selecting a
        level shows that level and everything above it, e.g. selecting
        "Warning" shows Warning, Error and Critical)
      - a checkbox to show/hide user input/output (executed code, results,
        stdout/stderr, display data)
      - a free-text search field ("user input") to only show matching lines

    All of these filters apply not only to newly incoming content, but also
    retroactively to the already buffered history (see
    ``ConsoleHandler.refresh``), so switching filters re-renders the whole
    console output including everything that was logged/executed before the
    filter was changed.
    """

    filter_changed = QtCore.Signal()

    LEVELS = [
        (logging.DEBUG, "Debug"),
        (logging.INFO, "Info"),
        (logging.WARNING, "Warning"),
        (logging.ERROR, "Error"),
        (logging.CRITICAL, "Critical"),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        self.setLayout(layout)

        title = QtWidgets.QLabel("Log Filter")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        # radio buttons: only one minimum level can be selected at a time.
        # selecting a level shows that level and everything above it
        # (e.g. "Warning" -> Warning, Error, Critical).
        self.level_radios: dict[int, QtWidgets.QRadioButton] = {}
        self._min_level = logging.INFO

        for level, name in self.LEVELS:
            radio = QtWidgets.QRadioButton(name)
            radio.setChecked(level == self._min_level)
            radio.toggled.connect(self._make_level_handler(level))
            self.level_radios[level] = radio
            layout.addWidget(radio)

        layout.addSpacing(10)

        # checkbox to show/hide the interactive user input/output
        # (executed commands, their results, stdout/stderr, display data)
        self.io_checkbox = QtWidgets.QCheckBox("User Input/Output")
        self.io_checkbox.setChecked(True)
        self.io_checkbox.stateChanged.connect(self._on_io_changed)
        layout.addWidget(self.io_checkbox)

        layout.addSpacing(10)

        search_label = QtWidgets.QLabel("Search")
        layout.addWidget(search_label)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("filter text...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        layout.addStretch()

        self.setMaximumWidth(150)

    def _make_level_handler(self, level: int) -> Any:
        def handler(checked: bool) -> None:
            if checked:
                self._min_level = level
                self.filter_changed.emit()

        return handler

    def _on_search_changed(self, text: str) -> None:
        self.filter_changed.emit()

    def _on_io_changed(self, state: int) -> None:
        self.filter_changed.emit()

    @property
    def io_enabled(self) -> bool:
        return self.io_checkbox.isChecked()

    def level_enabled(self, levelno: int) -> bool:
        """
        Returns whether messages of the given level should be visible,
        i.e. whether levelno is at or above the currently selected
        minimum level.
        """
        return levelno >= self._min_level

    def matches(self, levelno: int, message: str) -> bool:
        if not self.level_enabled(levelno):
            return False

        search_text = self.search_input.text().strip().lower()
        if search_text and search_text not in message.lower():
            return False

        return True


class ConsoleHandler(logging.Handler):
    """Logging handler to emit to LoggingConsole"""

    # ansi color-codes per log-level
    LEVEL_COLORS: dict[int, str] = {
        logging.DEBUG: "\x1b[90m",       # gray
        logging.INFO: "\x1b[36m",        # cyan
        logging.WARNING: "\x1b[33m",     # yellow
        logging.ERROR: "\x1b[31m",       # red
        logging.CRITICAL: "\x1b[1;91m",  # bold bright red
    }
    RESET = "\x1b[0m"

    def __init__(self, console: ConsoleWidget, filter_panel: LogFilterPanel | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.console = console
        self.filter_panel = filter_panel
        self.signal = QSignaler()

        # make it thread safe: emit() might get called from worker threads,
        # the signal/slot connection makes sure the actual console update
        # happens on the gui thread.
        self.signal.log_message.connect(self._on_log_message)

        self.setFormatter(logging.Formatter(
            fmt="{asctime} {levelname} ({name}): {message}",
            datefmt="%H:%M:%S",
            style="{"
            ))

        # keep a full history of (seq, levelno, formatted message) so the
        # console can be fully re-rendered whenever the filter settings
        # change. The sequence number is shared with the console's
        # user-input/output records, so both kinds of content can be
        # interleaved in the correct chronological order on refresh.
        self._records: list[tuple[int, int, str]] = []

        if self.filter_panel is not None:
            self.filter_panel.filter_changed.connect(self.refresh)

        self.add_logger("openglider")
        #self.add_logger("gpufem")
    
    def add_logger(self, name: str) -> None:
        logger = logging.getLogger(name)
        logger.addHandler(self)

    def _get_color(self, levelno: int) -> str:
        color = ""
        best_level = -1

        for level, code in self.LEVEL_COLORS.items():
            if levelno >= level and level > best_level:
                best_level = level
                color = code

        return color

    def _colorize(self, levelno: int, message: str) -> str:
        color = self._get_color(levelno)
        if not color:
            return message

        return f"{color}{message}{self.RESET}"

    def _matches_filter(self, levelno: int, message: str) -> bool:
        if self.filter_panel is None:
            # fall back to the previous default behaviour (INFO and up)
            return levelno >= logging.INFO

        return self.filter_panel.matches(levelno, message)

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        seq = self.console.next_seq()

        # store for later re-filtering/re-ordering, then hand off to the
        # gui thread for immediate display (subject to the current filter).
        self._records.append((seq, record.levelno, msg))
        self.signal.log_message.emit(record.levelno, msg)

    def _on_log_message(self, levelno: int, message: str) -> None:
        if not self._matches_filter(levelno, message):
            return

        self.console.log_message(self._colorize(levelno, message))

    def refresh(self) -> None:
        """
        Re-renders the whole console output from the buffered history,
        applying the currently selected minimum level, search text and
        user-input/output visibility. This is what makes the filters apply
        to already-logged/executed (buffered) content, not just newly
        incoming messages.
        """
        io_enabled = self.filter_panel is None or self.filter_panel.io_enabled
        self.console.set_io_visible(io_enabled)

        self.console.clear()

        # merge log messages and user input/output records by their shared
        # sequence number, so everything is replayed in the order it
        # originally happened.
        entries: list[tuple[int, str, Any]] = [
            (seq, "log", (levelno, message))
            for seq, levelno, message in self._records
        ]

        if io_enabled:
            entries += [
                (seq, "io", text)
                for seq, text in self.console._io_records
            ]

        entries.sort(key=lambda entry: entry[0])

        for _, kind, payload in entries:
            if kind == "log":
                levelno, message = payload
                if self._matches_filter(levelno, message):
                    self.console.log_message(self._colorize(levelno, message))
            else:
                self.console.replay_io_text(payload)
