"""widgets.py — the custom pieces stock Qt controls don't cover.

The nav rail and drawer are the same shapes used across all three of these
apps; the score ring and the check delegate are this one's own. The ring is
kept because the score is the number this app exists to produce, and it
deserves to look different from a count.
"""
from PySide6.QtCore import (QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize,
                            Qt, Property, Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QSizePolicy, QStyle,
                               QStyledItemDelegate, QVBoxLayout, QWidget)

from . import icons
from .theme import MONO, STATUS_LABEL, STATUS_TOKEN

MONO_FAMILY = MONO.split(",")[0].strip("' ")

ROLE_CHECK = Qt.UserRole + 1
ROLE_KIND = Qt.UserRole + 2
ROLE_TITLE = Qt.UserRole + 3
ROLE_SUBTITLE = Qt.UserRole + 4
ROLE_STATUS = Qt.UserRole + 5
ROLE_BADGE = Qt.UserRole + 6


def mono_font(size, weight=QFont.Normal):
    font = QFont(MONO_FAMILY)
    font.setStyleHint(QFont.Monospace)
    font.setPointSize(size)
    font.setWeight(weight)
    return font


def ui_font(option, size, weight=QFont.Normal):
    font = QFont(option.font)
    font.setPointSize(size)
    font.setWeight(weight)
    return font


class NavButton(QAbstractButton):
    def __init__(self, kind, text, palette):
        super().__init__()
        self.kind = kind
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._c = palette
        self._hover = False

    def set_palette(self, palette):
        self._c = palette
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        c = self._c
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(6, 2, -6, -2)

        if self.isChecked():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(c["accent_wash"]))
            painter.drawRoundedRect(QRectF(rect), 6, 6)
        elif self._hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(c["surface"]))
            painter.drawRoundedRect(QRectF(rect), 6, 6)

        colour = c["accent"] if self.isChecked() else (
            c["text"] if self._hover else c["text_muted"])
        painter.drawPixmap(rect.left() + 10, rect.center().y() - 8,
                           icons.icon(self.kind, colour, 17).pixmap(17, 17))

        font = painter.font()
        font.setPointSize(12)
        font.setWeight(QFont.DemiBold if self.isChecked() else QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor(colour))
        painter.drawText(rect.adjusted(36, 0, -8, 0),
                         Qt.AlignVCenter | Qt.AlignLeft, self.text())
        painter.end()


class NavRail(QWidget):
    changed = Signal(int)

    def __init__(self, palette):
        super().__init__()
        self.setObjectName("NavRail")
        self.setFixedWidth(178)
        self._c = palette
        self._buttons = []
        self._indicator_y = 0.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(2)
        self._layout = layout
        self._anim = QPropertyAnimation(self, b"indicator_y", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def add_item(self, kind, text):
        button = NavButton(kind, text, self._c)
        index = len(self._buttons)
        button.clicked.connect(lambda _=False, i=index: self.select(i))
        self._buttons.append(button)
        self._layout.addWidget(button)
        if index == 0:
            button.setChecked(True)
        return button

    def finish(self):
        self._layout.addStretch()

    def select(self, index, emit=True):
        for i, button in enumerate(self._buttons):
            button.setChecked(i == index)
        self._anim.stop()
        self._anim.setStartValue(float(self._indicator_y))
        self._anim.setEndValue(float(self._buttons[index].y() + 8))
        self._anim.start()
        if emit:
            self.changed.emit(index)

    def set_palette(self, palette):
        self._c = palette
        for button in self._buttons:
            button.set_palette(palette)
        self.update()

    def get_indicator_y(self):
        return self._indicator_y

    def set_indicator_y(self, value):
        self._indicator_y = value
        self.update()

    indicator_y = Property(float, get_indicator_y, set_indicator_y)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._buttons:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._c["accent"]))
        painter.drawRoundedRect(QRectF(0, self._indicator_y, 2.5, 22), 1.2, 1.2)
        painter.end()


class ScoreRing(QWidget):
    """The score, drawn as a seal closing clockwise from the top. Kept from
    the first version of this app: it's the one number the whole tool exists
    to produce, so it shouldn't look like the counts beside it."""

    def __init__(self, palette, size=104):
        super().__init__()
        self.setFixedSize(size, size)
        self._c = palette
        self._value = None
        self._applicable = 0
        self._total = 0

    def set_palette(self, palette):
        self._c = palette
        self.update()

    def set_score(self, value, applicable, total):
        self._value, self._applicable, self._total = value, applicable, total
        self.update()

    def paintEvent(self, _event):
        c = self._c
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(9, 9, -9, -9)
        width = 7

        track = QPen(QColor(c["border"]))
        track.setWidth(width)
        track.setCapStyle(Qt.RoundCap)
        painter.setPen(track)
        painter.drawArc(rect, 0, 360 * 16)

        if self._value is not None:
            ring = QPen(QColor(c["accent"]))
            ring.setWidth(width)
            ring.setCapStyle(Qt.RoundCap)
            painter.setPen(ring)
            painter.drawArc(rect, 90 * 16, -int(360 * 16 * self._value / 100))

        # The count lives beside the ring, not inside it: at this diameter a
        # caption under the number overlaps the arc it belongs to.
        painter.setPen(QColor(c["text"]))
        painter.setFont(mono_font(24, QFont.DemiBold))
        painter.drawText(self.rect(), Qt.AlignCenter,
                         str(self._value) if self._value is not None else "—")
        painter.end()


class StatCard(QFrame):
    def __init__(self, label, palette):
        super().__init__()
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 12)
        layout.setSpacing(3)
        self.value = QLabel("—")
        self.value.setFont(mono_font(20, QFont.DemiBold))
        self.label = QLabel(label)
        self.label.setObjectName("SectionLabel")
        layout.addWidget(self.value)
        layout.addWidget(self.label)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, 2)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(*palette["shadow"]))
        self.setGraphicsEffect(shadow)

    def set_colour(self, colour):
        self.value.setStyleSheet(f"color:{colour}; background:transparent;")


class Sparkline(QWidget):
    """Score over time, oldest to newest. A dozen points and a line doesn't
    justify a charting dependency."""

    def __init__(self, palette):
        super().__init__()
        self.setMinimumHeight(120)
        self._c = palette
        self._points = []

    def set_palette(self, palette):
        self._c = palette
        self.update()

    def set_data(self, history):
        self._points = history
        self.update()

    def paintEvent(self, _event):
        c = self._c
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        scored = [(ts, s) for ts, s, _ in reversed(self._points) if s is not None]

        if len(scored) < 2:
            painter.setPen(QColor(c["text_faint"]))
            painter.drawText(rect, Qt.AlignCenter,
                             "Scan a few more times to see a trend."
                             if scored else "No scans recorded yet.")
            painter.end()
            return

        pad_x, pad_y = 26, 22
        w = max(rect.width() - 2 * pad_x, 1)
        h = max(rect.height() - 2 * pad_y - 12, 1)
        n = len(scored)
        pts = [QPointF(pad_x + w * i / (n - 1), pad_y + h * (1 - scored[i][1] / 100))
               for i in range(n)]

        fill = QPainterPath(QPointF(pts[0].x(), rect.height() - pad_y))
        for p in pts:
            fill.lineTo(p)
        fill.lineTo(pts[-1].x(), rect.height() - pad_y)
        fill.closeSubpath()
        colour = QColor(c["accent"])
        colour.setAlpha(38)
        painter.fillPath(fill, colour)

        pen = QPen(QColor(c["accent"]))
        pen.setWidthF(2.0)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(c["accent"]))
        painter.drawEllipse(pts[-1], 3.5, 3.5)

        painter.setPen(QColor(c["text_faint"]))
        painter.setFont(mono_font(9))
        painter.drawText(int(pad_x), rect.height() - 4, str(scored[0][1]))
        last = str(scored[-1][1])
        metrics = QFontMetrics(painter.font())
        painter.drawText(int(rect.width() - pad_x - metrics.horizontalAdvance(last)),
                         rect.height() - 4, last)
        painter.end()


class CheckDelegate(QStyledItemDelegate):
    """Two-line rows with a status pill. A check is a name, a state and a
    reason, which want different weights rather than three table columns."""

    ROW_HEIGHT = 54
    GROUP_HEIGHT = 30

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self._c = palette

    def set_palette(self, palette):
        self._c = palette

    def sizeHint(self, option, index):
        height = self.GROUP_HEIGHT if index.data(ROLE_KIND) == "group" else self.ROW_HEIGHT
        return QSize(option.rect.width(), height)

    def paint(self, painter, option, index):
        c = self._c
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect

        if index.data(ROLE_KIND) == "group":
            painter.fillRect(rect, QColor(c["surface_alt"]))
            painter.setPen(QPen(QColor(c["border"]), 1))
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
            painter.setFont(mono_font(10, QFont.DemiBold))
            painter.setPen(QColor(c["text_muted"]))
            painter.drawText(rect.adjusted(14, 0, -80, 0), Qt.AlignVCenter | Qt.AlignLeft,
                             index.data(ROLE_TITLE) or "")
            painter.setPen(QColor(c["text_faint"]))
            painter.drawText(rect.adjusted(0, 0, -14, 0), Qt.AlignVCenter | Qt.AlignRight,
                             index.data(ROLE_BADGE) or "")
            painter.restore()
            return

        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        status = index.data(ROLE_STATUS) or "unknown"
        token = STATUS_TOKEN.get(status, "na")

        if selected:
            painter.fillRect(rect, QColor(c["selection"]))
            painter.fillRect(QRectF(rect.left(), rect.top(), 2.5, rect.height()),
                             QColor(c["accent"]))
        elif hovered:
            painter.fillRect(rect, QColor(c["surface_alt"]))

        painter.setPen(QPen(QColor(c["border"]), 1))
        painter.drawLine(rect.left() + 14, rect.bottom(), rect.right() - 14, rect.bottom())

        pill = QRectF(rect.left() + 16, rect.center().y() - 9, 66, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(c[token + "_wash"]))
        painter.drawRoundedRect(pill, 4, 4)
        painter.setFont(mono_font(8, QFont.Bold))
        painter.setPen(QColor(c[token]))
        painter.drawText(pill, Qt.AlignCenter, STATUS_LABEL.get(status, status.upper()))

        left = rect.left() + 94
        width = rect.width() - (left - rect.left()) - 16

        painter.setFont(ui_font(option, 12, QFont.DemiBold if selected else QFont.Normal))
        painter.setPen(QColor(c["text"]))
        painter.drawText(left, rect.top() + 21,
                         self._elide(painter, index.data(ROLE_TITLE), width))

        painter.setFont(ui_font(option, 11))
        painter.setPen(QColor(c["text_faint"]))
        painter.drawText(left, rect.top() + 39,
                         self._elide(painter, index.data(ROLE_SUBTITLE), width))
        painter.restore()

    @staticmethod
    def _elide(painter, text, width):
        return QFontMetrics(painter.font()).elidedText(text or "", Qt.ElideRight, int(width))


class Drawer(QFrame):
    closed = Signal()

    def __init__(self, parent, width=300):
        super().__init__(parent)
        self.setObjectName("Drawer")
        self._width = width
        self._open = False

        self.scrim = QWidget(parent)
        self.scrim.setObjectName("Scrim")
        self.scrim.hide()
        self.scrim.mousePressEvent = lambda _e: self.close_drawer()

        self.header = QWidget()
        self.header.setObjectName("DrawerHeader")
        self.header.setFixedHeight(44)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(14, 0, 8, 0)
        self.title = QLabel("")
        self.title.setObjectName("SectionLabel")
        header_layout.addWidget(self.title)
        header_layout.addStretch()
        self._header_layout = header_layout

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(14, 14, 14, 14)
        self.body_layout.setSpacing(10)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.body, 1)

        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(230)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.hide()

    def add_header_button(self, widget):
        self._header_layout.addWidget(widget)

    def reposition(self):
        parent = self.parentWidget()
        if not parent:
            return
        self.resize(self._width, parent.height())
        self.scrim.setGeometry(0, 0, parent.width(), parent.height())
        self.move(parent.width() - self._width if self._open else parent.width(), 0)

    def open_drawer(self, title=""):
        parent = self.parentWidget()
        if not parent or self._open:
            return
        if title:
            self.title.setText(title)
        self._open = True
        self.resize(self._width, parent.height())
        self.scrim.setGeometry(0, 0, parent.width(), parent.height())
        self.scrim.show()
        self.scrim.raise_()
        self.move(parent.width(), 0)
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self.pos().__class__(parent.width() - self._width, 0))
        self._anim.start()

    def close_drawer(self):
        parent = self.parentWidget()
        if not parent or not self._open:
            return
        self._open = False
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self.pos().__class__(parent.width(), 0))

        def finish():
            if not self._open:
                self.hide()
                self.scrim.hide()
                self.closed.emit()
            try:
                self._anim.finished.disconnect(finish)
            except RuntimeError:
                pass

        self._anim.finished.connect(finish)
        self._anim.start()

    def toggle(self, title=""):
        self.close_drawer() if self._open else self.open_drawer(title)

    @property
    def is_open(self):
        return self._open
