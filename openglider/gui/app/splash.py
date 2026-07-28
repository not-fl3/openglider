from __future__ import annotations

from collections import deque
import logging
import os

from openglider.gui.qt import QtCore, QtGui, QtWidgets


class SplashScreen(QtWidgets.QSplashScreen):
    def __init__(self, pixmap: QtGui.QPixmap, log_area_height: int, window_flags: QtCore.Qt.WindowType):
        super().__init__(pixmap, window_flags)
        self.log_area_height = log_area_height
        self.log_lines: list[str] = []
        self.log_padding_x = 22
        self.log_padding_top = 14
        self.log_padding_bottom = 10
        self.log_font = QtGui.QFont("DejaVu Sans Mono", 10)
        self.log_color = QtGui.QColor(230, 235, 242)

    def set_log_lines(self, lines: list[str]) -> None:
        self.log_lines = lines
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)

        if not self.log_lines:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self.log_font)
        painter.setPen(self.log_color)

        clip_rect = QtCore.QRect(
            self.log_padding_x,
            self.log_padding_top,
            max(0, self.width() - (2 * self.log_padding_x)),
            max(0, self.log_area_height - self.log_padding_top - self.log_padding_bottom),
        )

        painter.setClipRect(clip_rect)

        metrics = QtGui.QFontMetrics(self.log_font)
        line_height = max(1, metrics.height())
        lines = [metrics.elidedText(line, QtCore.Qt.TextElideMode.ElideRight, clip_rect.width()) for line in self.log_lines]

        max_visible_lines = max(1, clip_rect.height() // line_height)
        visible_lines = lines[-max_visible_lines:]
        y = clip_rect.top() + metrics.ascent()

        for line in visible_lines:
            painter.drawText(clip_rect.left(), y, line)
            y += line_height

        painter.end()


class _SplashLogEmitter(QtCore.QObject):
    message = QtCore.Signal(str)


class SplashLogHandler(logging.Handler):
    def __init__(self, splash: QtWidgets.QSplashScreen, max_lines: int = 200):
        super().__init__(level=logging.INFO)
        self.splash = splash
        self.lines: deque[str] = deque(maxlen=max_lines)
        self._emitter = _SplashLogEmitter()
        self._emitter.message.connect(self._append_line)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()

        self._emitter.message.emit(message)

    def _append_line(self, line: str) -> None:
        if self.splash is None:
            return

        text = line.strip()
        if not text:
            return

        self.lines.append(text)
        if isinstance(self.splash, SplashScreen):
            self.splash.set_log_lines(list(self.lines))
        else:
            self.splash.showMessage(
                "\n".join(self.lines),
                int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop),
                QtGui.QColor(230, 235, 242),
            )
            self.splash.repaint()


def create_splash_log_handler(splash: QtWidgets.QSplashScreen) -> SplashLogHandler:
    handler = SplashLogHandler(splash)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def create_splash_screen(version: str, logger: logging.Logger | None = None) -> QtWidgets.QSplashScreen | None:
    image_path = os.path.join(os.path.dirname(__file__), "screenshot.png")
    if not os.path.isfile(image_path):
        if logger is not None:
            logger.warning(f"Splash image not found: {image_path}")
        return None

    original = QtGui.QPixmap(image_path)
    if original.isNull():
        if logger is not None:
            logger.warning(f"Could not load splash image: {image_path}")
        return None

    scaled = original.scaled(
        1100,
        720,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )

    log_area_height = int(scaled.height() * 0.6)
    rounded = QtGui.QPixmap(scaled.size())
    rounded.fill(QtCore.Qt.GlobalColor.transparent)

    radius = 26.0
    rect = QtCore.QRectF(rounded.rect())
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, radius, radius)

    painter = QtGui.QPainter(rounded)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)

    # Subtle overlay for top log readability on bright image regions.
    log_overlay = QtCore.QRectF(0.0, 0.0, rect.width(), float(log_area_height))
    log_gradient = QtGui.QLinearGradient(log_overlay.topLeft(), log_overlay.bottomLeft())
    log_gradient.setColorAt(0.0, QtGui.QColor(10, 14, 20, 135))
    log_gradient.setColorAt(1.0, QtGui.QColor(10, 14, 20, 0))
    painter.fillRect(log_overlay, log_gradient)

    title = f"openglider v {version}"
    title_height = 90.0
    title_margin = 36.0
    title_rect = QtCore.QRectF(
        title_margin,
        rect.height() - title_height - 30.0,
        rect.width() - (2 * title_margin),
        title_height,
    )

    painter.setClipping(False)

    fade_height = min(220.0, rect.height() * 0.4)
    fade_rect = QtCore.QRectF(0.0, rect.height() - fade_height, rect.width(), fade_height)
    fade_gradient = QtGui.QLinearGradient(fade_rect.topLeft(), fade_rect.bottomLeft())
    fade_gradient.setColorAt(0.0, QtGui.QColor(16, 22, 30, 0))
    fade_gradient.setColorAt(1.0, QtGui.QColor(16, 22, 30, 165))
    painter.fillRect(fade_rect, fade_gradient)

    font = QtGui.QFont("DejaVu Sans", 28)
    font.setBold(True)
    painter.setFont(font)

    shadow_rect = title_rect.translated(2.0, 2.0)
    painter.setPen(QtGui.QColor(0, 0, 0, 170))
    painter.drawText(
        shadow_rect,
        int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignHCenter),
        title,
    )

    text_gradient = QtGui.QLinearGradient(title_rect.topLeft(), title_rect.bottomLeft())
    text_gradient.setColorAt(0.0, QtGui.QColor(255, 255, 255))
    text_gradient.setColorAt(1.0, QtGui.QColor(228, 236, 248))
    painter.setPen(QtGui.QPen(QtGui.QBrush(text_gradient), 1.0))
    painter.drawText(
        title_rect,
        int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignHCenter),
        title,
    )

    accent_y = int(title_rect.top() - 8)
    painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 170), 2.0))
    painter.drawLine(int(title_margin), accent_y, int(rect.width() - title_margin), accent_y)
    painter.end()

    splash = SplashScreen(
        rounded,
        log_area_height,
        QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint,
    )

    splash.setMask(QtGui.QRegion(path.toFillPolygon().toPolygon()))
    splash.set_log_lines(["Starting OpenGlider..."])
    return splash


class SplashController:
    def __init__(
        self,
        version: str,
        logger: logging.Logger,
        default_delay_ms: int,
    ):
        self._logger = logger
        self._default_delay_ms = default_delay_ms
        self.splash = create_splash_screen(version, logger=logger)
        self._log_handler: SplashLogHandler | None = None

    def show(self) -> None:
        if self.splash is None:
            return

        self.splash.show()
        self.splash.raise_()
        self.splash.repaint()

        self._log_handler = create_splash_log_handler(self.splash)
        logging.getLogger().addHandler(self._log_handler)

    def schedule_finish(self, main_window: QtWidgets.QWidget) -> None:
        if self.splash is None:
            return

        delay_ms = self._get_delay_ms()
        if delay_ms > 0:
            QtCore.QTimer.singleShot(delay_ms, lambda: self.finish(main_window))
        else:
            self.finish(main_window)

    def finish(self, main_window: QtWidgets.QWidget) -> None:
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler.close()
            self._log_handler = None

        if self.splash is not None:
            self.splash.finish(main_window)
            self.splash = None

    def _get_delay_ms(self) -> int:
        delay_ms = self._default_delay_ms
        env_delay = os.environ.get("OPENGLIDER_SPLASH_DELAY_MS")
        if env_delay is not None:
            try:
                delay_ms = max(0, int(env_delay))
            except ValueError:
                self._logger.warning(f"Invalid OPENGLIDER_SPLASH_DELAY_MS value: {env_delay}")

        return delay_ms
