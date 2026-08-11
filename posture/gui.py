"""gui.py — posture auditor desktop app (PySide6).

Same design system as Kevscope (its sibling app, separate codebase on
purpose): a cool, token-driven light/dark theme, tabs instead of a side
panel for detail views, and the handful of motion moments done explicitly
with QPropertyAnimation/QVariantAnimation since Qt Style Sheets have no CSS
transitions. Reused as a pattern, not imported — two projects isn't enough
signal yet to know what should actually be a shared library.

Launch:  python3 -m posture        (or python3 -m posture.gui)
"""
import html
import sys
import time
import traceback

from PySide6.QtCore import (
    Qt, QEasingCurve, QObject, QPointF, QPropertyAnimation, QRunnable,
    QSettings, QThreadPool, QTimer, QVariantAnimation, Signal, Slot,
)
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QTabBar, QTabWidget, QVBoxLayout, QWidget,
)

from . import store, warn_if_root
from .checks import ALL_CHECKS
from .checks.base import STATUS_FAIL, STATUS_NA, STATUS_PASS, STATUS_UNKNOWN
from .scoring import run_all, score

PALETTES = {
    "dark": {
        "bg": "#0B0F14", "surface": "#121820", "surface_alt": "#0E141B",
        "border": "#212B37", "text": "#E7EDF3", "text_muted": "#7C8B9C",
        "accent": "#45D8C4", "accent_ink": "#06201C",
        "danger": "#F2545B", "warning": "#F5A623", "success": "#34D399",
        "row_fail_bg": "#241419", "shadow": (0, 0, 0, 110),
    },
    "light": {
        "bg": "#F6F8FA", "surface": "#FFFFFF", "surface_alt": "#EEF2F5",
        "border": "#DCE3E9", "text": "#16202B", "text_muted": "#5B6B7C",
        "accent": "#0E9488", "accent_ink": "#FFFFFF",
        "danger": "#D8394A", "warning": "#B96C08", "success": "#12946B",
        "row_fail_bg": "#FCEBEC", "shadow": (30, 40, 60, 45),
    },
}

_STATUS_TEXT = {STATUS_PASS: "Pass", STATUS_FAIL: "Needs attention",
               STATUS_UNKNOWN: "Couldn't determine", STATUS_NA: "Not applicable"}


def _esc(v):
    return html.escape(str(v)) if v is not None else ""


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _build_qss(c):
    return f"""
QMainWindow, QWidget {{ background: {c['bg']}; color: {c['text']};
    font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 13px; }}
#Title {{ font-size: 24px; font-weight: 700; color: {c['text']}; letter-spacing: -0.3px; }}
#Eyebrow {{ color: {c['accent']}; font-size: 10px; font-weight: 700; letter-spacing: 2.2px; }}
#Sub {{ color: {c['text_muted']}; font-size: 13px; }}
QPushButton {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']};
    border-radius: 8px; padding: 8px 16px; font-size: 12px; font-weight: 500; }}
QPushButton:hover {{ border-color: {c['accent']}; color: {c['accent']}; }}
QPushButton:pressed {{ background: {c['surface_alt']}; }}
QPushButton:disabled {{ color: {c['text_muted']}; border-color: {c['border']}; }}
QPushButton#Primary {{ background: {c['accent']}; color: {c['accent_ink']}; border: none; font-weight: 700; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid transparent; padding: 8px 10px; }}
QPushButton#Ghost:hover {{ background: {c['surface']}; border-color: {c['border']}; color: {c['text']}; }}
QFrame#KpiCard {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QLabel#KpiVal {{ background: transparent; }}
QLabel#KpiLbl {{ color: {c['text_muted']}; font-size: 10px; font-weight: 700; letter-spacing: 1.1px; background: transparent; }}
QLabel#KpiTrend {{ font-size: 10px; font-weight: 600; background: transparent; }}
QLabel#DetailBody {{ font-size: 12px; background: transparent; padding: 14px; }}
QScrollArea {{ border: none; background: transparent; }}
QLineEdit, QComboBox {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']};
    border-radius: 8px; padding: 7px 11px; font-size: 12px; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: {c['surface']}; color: {c['text']};
    border: 1px solid {c['border']}; selection-background-color: {_rgba(c['accent'], 35)}; }}
QTableWidget {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px;
    gridline-color: {c['border']}; alternate-background-color: {c['surface_alt']}; }}
QHeaderView::section {{ background: {c['surface']}; color: {c['text_muted']}; border: none;
    border-bottom: 1px solid {c['border']}; padding: 10px 10px; font-size: 10px;
    font-weight: 700; letter-spacing: 1.1px; }}
QTableWidget::item {{ padding: 8px 10px; border-bottom: 1px solid {c['border']}; }}
QTableWidget::item:selected {{ background: {_rgba(c['accent'], 40)}; }}
QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 14px; top: -1px; background: {c['surface']}; }}
QTabBar::tab {{ background: transparent; color: {c['text_muted']}; padding: 8px 16px;
    margin-right: 2px; border: none; border-bottom: 2px solid transparent; font-size: 12px; font-weight: 500; }}
QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
QTabBar::tab:hover {{ color: {c['text']}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 5px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QStatusBar {{ color: {c['text_muted']}; font-size: 11px; }}
"""


class _Signals(QObject):
    done = Signal(object)
    error = Signal(str)


class _Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()

    @Slot()
    def run(self):
        try:
            self.signals.done.emit(self.fn(*self.args, **self.kwargs))
        except Exception:
            self.signals.error.emit(traceback.format_exc().strip().splitlines()[-1])


class KpiCard(QFrame):
    """One stat card: accent top bar + big monospace number + muted label,
    hover deepens its shadow. Same widget shape as Kevscope's, since this is
    exactly the kind of small proven pattern worth reusing across sibling
    apps without formally sharing code for it."""
    def __init__(self, label_text):
        super().__init__()
        self.setObjectName("KpiCard")

        self.bar = QFrame()
        self.bar.setFixedHeight(3)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 13, 16, 14)
        bl.setSpacing(6)

        self.value_label = QLabel("—")
        self.value_label.setObjectName("KpiVal")
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        mono.setPointSize(21)
        mono.setWeight(QFont.DemiBold)
        self.value_label.setFont(mono)

        self.label_widget = QLabel(label_text)
        self.label_widget.setObjectName("KpiLbl")

        self.trend_label = QLabel("")
        self.trend_label.setObjectName("KpiTrend")
        self.trend_label.hide()

        bl.addWidget(self.value_label)
        bl.addWidget(self.label_widget)
        bl.addWidget(self.trend_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.bar)
        outer.addWidget(body)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 5)
        self._shadow.setBlurRadius(14)
        self.setGraphicsEffect(self._shadow)
        self._shadow_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._shadow_anim.setDuration(160)
        self._shadow_anim.setEasingCurve(QEasingCurve.OutCubic)

    def set_theme(self, accent_hex, shadow_rgba):
        self.value_label.setStyleSheet(f"color:{accent_hex}")
        self.bar.setStyleSheet(f"background:{accent_hex}; border-top-left-radius:14px; "
                               f"border-top-right-radius:14px;")
        self._shadow.setColor(QColor(*shadow_rgba))

    def set_trend(self, text, color_hex):
        """text=None hides the trend line entirely (first scan ever, or a
        KPI that doesn't track a trend) rather than showing a stale one."""
        if text:
            self.trend_label.setText(text)
            self.trend_label.setStyleSheet(f"color:{color_hex}")
            self.trend_label.show()
        else:
            self.trend_label.hide()

    def _animate_shadow(self, to):
        self._shadow_anim.stop()
        self._shadow_anim.setStartValue(self._shadow.blurRadius())
        self._shadow_anim.setEndValue(to)
        self._shadow_anim.start()

    def enterEvent(self, event):
        self._animate_shadow(28)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_shadow(14)
        super().leaveEvent(event)


class Sparkline(QWidget):
    """A hand-painted line chart, oldest scan to newest, left to right. No
    charting library dependency for what's fundamentally a dozen points and
    a line — QPainter on a QWidget is the whole implementation."""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(140)
        self._points = []           # [(ts, score_or_None, applicable), ...] most-recent-first
        self._line_hex = "#45D8C4"
        self._text_hex = "#7C8B9C"

    def set_theme(self, line_hex, text_hex):
        self._line_hex = line_hex
        self._text_hex = text_hex
        self.update()

    def set_data(self, history):
        self._points = history
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        scored = [(ts, s) for ts, s, _ in reversed(self._points) if s is not None]

        if len(scored) < 2:
            painter.setPen(QColor(self._text_hex))
            msg = "Scan a few more times to see a trend here." if scored else "No scans recorded yet."
            painter.drawText(rect, Qt.AlignCenter, msg)
            painter.end()
            return

        pad_x, pad_y = 24, 20
        w = max(rect.width() - 2 * pad_x, 1)
        h = max(rect.height() - 2 * pad_y, 1)
        n = len(scored)
        pts = [QPointF(pad_x + (w * i / (n - 1)), pad_y + h * (1 - scored[i][1] / 100)) for i in range(n)]

        pen = QPen(QColor(self._line_hex))
        pen.setWidthF(2.0)
        painter.setPen(pen)
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._line_hex))
        for p in pts:
            painter.drawEllipse(p, 3, 3)

        painter.setPen(QColor(self._text_hex))
        painter.drawText(int(pad_x), int(rect.height() - 4), f"{scored[0][1]}")
        last_label = f"{scored[-1][1]}"
        fm = painter.fontMetrics()
        painter.drawText(int(rect.width() - pad_x - fm.horizontalAdvance(last_label)),
                         int(rect.height() - 4), last_label)
        painter.end()


COLS = ["Check", "Severity", "Status", "Detail"]
KPI_ROLES = {"score": "accent", "passed": "success", "gaps": "danger", "unknown": "warning"}


class MainWindow(QMainWindow):
    def __init__(self, auto_scan=True):
        super().__init__()
        self.setWindowTitle("Posture")
        self.resize(1000, 660)
        self.pool = QThreadPool.globalInstance()
        self._results = []
        self._rendered_rows = []
        self.detail_tabs = {}
        self._permanent_tabs = set()   # widgets that must never be closed, checked by identity, not index
        self._kpi_prev = {"score": 0, "passed": 0, "gaps": 0, "unknown": 0}
        self._anim_refs = []
        self._workers = []

        self._settings = QSettings("Fluid-Prism", "Posture")
        saved = self._settings.value("theme")
        self.theme = saved if saved in PALETTES else self._detect_system_theme()
        self.c = PALETTES[self.theme]

        self._build_ui()
        self._apply_theme(self.theme, first_load=True)
        if auto_scan:
            self.on_scan()

    @staticmethod
    def _detect_system_theme():
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Light:
                return "light"
        except Exception:
            pass
        return "dark"

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(22, 20, 22, 14)
        v.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        eye = QLabel("SECURITY POSTURE"); eye.setObjectName("Eyebrow")
        title = QLabel("This machine"); title.setObjectName("Title")
        sub = QLabel("Hardening basics, scored honestly, fixed one gap at a time.")
        sub.setObjectName("Sub")
        titles.addWidget(eye); titles.addWidget(title); titles.addWidget(sub)
        head.addLayout(titles)
        head.addStretch()

        self.btn_theme = QPushButton(); self.btn_theme.setObjectName("Ghost")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.on_theme_toggle)
        self.btn_scan = QPushButton("Scan"); self.btn_scan.setObjectName("Primary")
        self.btn_scan.clicked.connect(self.on_scan)
        for b in (self.btn_theme, self.btn_scan):
            b.setCursor(Qt.PointingHandCursor)
            head.addWidget(b)
        v.addLayout(head)

        self.kpi_cards = {}
        krow = QHBoxLayout(); krow.setSpacing(14)
        for key, label in [("score", "POSTURE SCORE"), ("passed", "CHECKS PASSED"),
                           ("gaps", "GAPS FOUND"), ("unknown", "COULDN'T DETERMINE")]:
            card = KpiCard(label)
            krow.addWidget(card)
            self.kpi_cards[key] = card
        v.addLayout(krow)
        self._kpi_anims = {k: self._make_kpi_anim(k) for k in KPI_ROLES}

        frow = QHBoxLayout(); frow.setSpacing(10)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search a check…")
        self.search.textChanged.connect(self._render)
        self.f_status = QComboBox()
        self.f_status.addItems(["All", "Needs attention", "Pass", "Couldn't determine"])
        self.f_status.currentIndexChanged.connect(self._render)
        for w in (self.search, self.f_status):
            w.setCursor(Qt.PointingHandCursor if isinstance(w, QComboBox) else Qt.IBeamCursor)
        frow.addWidget(self.search, 1)
        frow.addWidget(self.f_status)
        self.count = QLabel(""); self.count.setObjectName("Sub")
        frow.addWidget(self.count)
        v.addLayout(frow)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setMinimumSectionSize(70)
        self.table.cellClicked.connect(self._on_cell_clicked)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.addTab(self.table, "Overview")
        self.tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)
        self._permanent_tabs.add(self.table)

        history_tab = QWidget()
        hl = QVBoxLayout(history_tab)
        hl.setContentsMargins(16, 14, 16, 14)
        hl.setSpacing(12)
        self.sparkline = Sparkline()
        hl.addWidget(self.sparkline)
        self.history_list = QLabel()
        self.history_list.setObjectName("DetailBody")
        self.history_list.setWordWrap(True)
        self.history_list.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.history_list.setTextFormat(Qt.RichText)
        history_scroll = QScrollArea()
        history_scroll.setWidgetResizable(True)
        history_scroll.setWidget(self.history_list)
        hl.addWidget(history_scroll, 1)
        history_idx = self.tabs.addTab(history_tab, "History")
        self.tabs.tabBar().setTabButton(history_idx, QTabBar.RightSide, None)
        self._permanent_tabs.add(history_tab)

        v.addWidget(self.tabs, 1)

        self.statusBar().showMessage("Ready")

    def _make_kpi_anim(self, key):
        anim = QVariantAnimation(self)
        anim.setDuration(650)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.valueChanged.connect(lambda val, k=key: self.kpi_cards[k].value_label.setText(str(int(val))))
        return anim

    # ── Theme ────────────────────────────────────────────────────────────────
    def on_theme_toggle(self):
        new_theme = "light" if self.theme == "dark" else "dark"
        central = self.centralWidget()
        fade_out_ms = 110
        self._fade(central, 1.0, 0.0, fade_out_ms)
        QTimer.singleShot(int(fade_out_ms * 0.6), lambda: self._apply_theme(new_theme))
        QTimer.singleShot(fade_out_ms, lambda: self._fade(central, 0.0, 1.0, 160))

    def _apply_theme(self, name, first_load=False):
        self.theme = name
        self.c = PALETTES[name]
        self._settings.setValue("theme", name)
        self.setStyleSheet(_build_qss(self.c))
        self.btn_theme.setText("☾  Dark" if name == "light" else "☀  Light")
        for key, role in KPI_ROLES.items():
            self.kpi_cards[key].set_theme(self.c[role], self.c["shadow"])
        self._refresh_history()
        if not first_load:
            if self._rendered_rows:
                self._recolor_table()
            for tab in self.detail_tabs.values():
                self._render_detail_tab(tab)

    def _refresh_history(self):
        """Called after every scan and on every theme change — the sparkline
        and score trend both depend on theme colors, and the trend depends
        on data that changes with each new scan."""
        history = store.score_history(limit=30)
        self.sparkline.set_theme(self.c["accent"], self.c["text_muted"])
        self.sparkline.set_data(history)
        self._render_history_list(history)
        self._update_score_trend(history)

    def _render_history_list(self, history):
        c = self.c
        if not history:
            self.history_list.setText(f"<div style='color:{c['text_muted']}'>No scans recorded yet.</div>")
            return
        rows = []
        for ts, s, applicable in history:
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
            score_text = f"{s}/100" if s is not None else "—"
            rows.append(f"<div><b>{_esc(when)}</b> &middot; {_esc(score_text)} "
                        f"<span style='color:{c['text_muted']}'>({applicable} of {len(ALL_CHECKS)} "
                        f"determinable)</span></div>")
        self.history_list.setText("".join(rows))

    def _update_score_trend(self, history):
        scored = [(ts, s) for ts, s, _ in history if s is not None]
        card = self.kpi_cards["score"]
        if len(scored) < 2:
            card.set_trend(None, self.c["text_muted"])
            return
        delta = scored[0][1] - scored[1][1]
        if delta > 0:
            card.set_trend(f"↑ +{delta} since last scan", self.c["success"])
        elif delta < 0:
            card.set_trend(f"↓ {delta} since last scan", self.c["danger"])
        else:
            card.set_trend("No change since last scan", self.c["text_muted"])

    def _fade(self, widget, start, end, duration, on_finished=None):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim_refs.append(anim)

        def _cleanup():
            if anim in self._anim_refs:
                self._anim_refs.remove(anim)
            widget.setGraphicsEffect(None)

        anim.finished.connect(_cleanup)
        if on_finished:
            anim.finished.connect(on_finished)
        anim.start()
        return anim

    def _animate_kpi(self, key, new_value):
        anim = self._kpi_anims[key]
        anim.stop()
        anim.setStartValue(self._kpi_prev.get(key, 0))
        anim.setEndValue(new_value)
        anim.start()
        self._kpi_prev[key] = new_value

    def _stagger_kpi(self, key, value, delay_ms):
        QTimer.singleShot(delay_ms, lambda: self._animate_kpi(key, value))

    # ── Actions ─────────────────────────────────────────────────────────────
    def on_scan(self):
        self.btn_scan.setEnabled(False)
        self.statusBar().showMessage("Checking this machine…")
        w = _Worker(self._run_and_record)
        self._workers.append(w)

        def _cleanup(*_):
            if w in self._workers:
                self._workers.remove(w)

        w.signals.done.connect(self._on_data)
        w.signals.done.connect(_cleanup)
        w.signals.error.connect(self._on_error)
        w.signals.error.connect(_cleanup)
        self.pool.start(w)

    @staticmethod
    def _run_and_record():
        results = run_all(ALL_CHECKS)
        s, applicable = score(results)
        store.record_scan(results, s, applicable)
        return results

    @Slot(object)
    def _on_data(self, results):
        self._results = results
        passed = sum(1 for _, r in results if r.status == STATUS_PASS)
        failed = sum(1 for _, r in results if r.status == STATUS_FAIL)
        unknown = sum(1 for _, r in results if r.status in (STATUS_UNKNOWN, STATUS_NA))
        s, applicable = score(results)

        self._stagger_kpi("passed", passed, 0)
        self._stagger_kpi("gaps", failed, 70)
        self._stagger_kpi("unknown", unknown, 140)
        if s is not None:
            self._stagger_kpi("score", s, 210)
        else:
            self._kpi_anims["score"].stop()
            self.kpi_cards["score"].value_label.setText("—")

        self._render()
        QTimer.singleShot(90, lambda: self._fade(self.table, 0.0, 1.0, 220))
        QTimer.singleShot(260, self._refresh_history)   # just after the score KPI settles
        self.btn_scan.setEnabled(True)
        self.statusBar().showMessage(
            f"{passed} passed · {failed} need attention · {unknown} couldn't determine · "
            f"updated {time.strftime('%H:%M:%S')}"
        )

    @Slot(str)
    def _on_error(self, msg):
        self.btn_scan.setEnabled(True)
        self.statusBar().showMessage(f"Error: {msg}")

    # ── Rendering + filtering ────────────────────────────────────────────────
    def _render(self):
        if not self._results:
            return
        c = self.c
        q = self.search.text().lower().strip()
        fs = self.f_status.currentText()

        rows = []
        for check, result in self._results:
            if q and q not in check.title.lower():
                continue
            if fs == "Needs attention" and result.status != STATUS_FAIL:
                continue
            if fs == "Pass" and result.status != STATUS_PASS:
                continue
            if fs == "Couldn't determine" and result.status not in (STATUS_UNKNOWN, STATUS_NA):
                continue
            rows.append((check, result))

        self._rendered_rows = rows
        self.count.setText(f"{len(rows)} of {len(self._results)}")
        self.table.setRowCount(len(rows))
        mono = QFont("Menlo"); mono.setStyleHint(QFont.Monospace); mono.setPointSize(11)
        for i, (check, result) in enumerate(rows):
            cells = [check.title, check.severity.capitalize(), _STATUS_TEXT[result.status], result.detail]
            for j, text in enumerate(cells):
                it = QTableWidgetItem(text)
                if j in (1, 2):
                    it.setFont(mono)
                if j == 2:
                    it.setForeground(QColor({
                        STATUS_PASS: c["success"], STATUS_FAIL: c["danger"],
                        STATUS_UNKNOWN: c["warning"], STATUS_NA: c["text_muted"],
                    }[result.status]))
                if result.status == STATUS_FAIL:
                    it.setBackground(QColor(c["row_fail_bg"]))
                self.table.setItem(i, j, it)

    def _recolor_table(self):
        c = self.c
        for i, (check, result) in enumerate(self._rendered_rows):
            status_item = self.table.item(i, 2)
            if status_item:
                status_item.setForeground(QColor({
                    STATUS_PASS: c["success"], STATUS_FAIL: c["danger"],
                    STATUS_UNKNOWN: c["warning"], STATUS_NA: c["text_muted"],
                }[result.status]))
            if result.status == STATUS_FAIL:
                for j in range(len(COLS)):
                    it = self.table.item(i, j)
                    if it:
                        it.setBackground(QColor(c["row_fail_bg"]))

    # ── Detail tabs ──────────────────────────────────────────────────────────
    def _on_cell_clicked(self, row, _column):
        if row < 0 or row >= len(self._rendered_rows):
            return
        self._open_detail_tab(*self._rendered_rows[row])

    def _open_detail_tab(self, check, result):
        key = check.id
        existing = self.detail_tabs.get(key)
        if existing:
            idx = self.tabs.indexOf(existing["container"])
            if idx != -1:
                self.tabs.setCurrentIndex(idx)
                return
            del self.detail_tabs[key]

        body = QLabel()
        body.setObjectName("DetailBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        body.setTextFormat(Qt.RichText)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)

        tab = {"check": check, "result": result, "body": body, "container": scroll}
        self.detail_tabs[key] = tab
        self._render_detail_tab(tab)

        title = check.title if len(check.title) <= 24 else check.title[:23] + "…"
        idx = self.tabs.addTab(scroll, title)
        self.tabs.setCurrentIndex(idx)

    def _render_detail_tab(self, tab):
        tab["body"].setText(self._detail_html(tab["check"], tab["result"]))

    def _close_tab(self, index):
        widget = self.tabs.widget(index)
        if widget in self._permanent_tabs:
            return   # Overview and History — checked by identity, not index, so this
                     # can't silently stop protecting a tab if the tab order ever changes
        for key, tab in list(self.detail_tabs.items()):
            if tab["container"] is widget:
                del self.detail_tabs[key]
                break
        self.tabs.removeTab(index)
        widget.deleteLater()

    def _detail_html(self, check, result):
        c = self.c
        status_color = {STATUS_PASS: c["success"], STATUS_FAIL: c["danger"],
                        STATUS_UNKNOWN: c["warning"], STATUS_NA: c["text_muted"]}[result.status]
        parts = [
            f"<div style='font-size:16px;font-weight:600;color:{c['text']}'>{_esc(check.title)}</div>",
            f"<div style='color:{c['text_muted']};font-size:11px;margin-bottom:10px'>"
            f"<span style='color:{status_color}'>{_esc(_STATUS_TEXT[result.status])}</span>"
            f" &middot; {_esc(check.severity.capitalize())} severity"
            f" &middot; {_esc(check.cis_topic)}</div>",
            f"<div style='color:{status_color}'>{_esc(result.detail)}</div>",
            f"<hr style='border-color:{c['border']};margin:12px 0'>",
            f"<div style='color:{c['accent']};font-size:10px;font-weight:700;"
            f"letter-spacing:1.1px;margin-bottom:6px'>WHY IT MATTERS</div>",
            f"<div style='color:{c['text_muted']}'>{_esc(check.rationale)}</div>",
        ]
        if result.status == STATUS_FAIL:
            parts.append(f"<div style='color:{c['accent']};font-size:10px;font-weight:700;"
                        f"letter-spacing:1.1px;margin-top:14px;margin-bottom:6px'>HOW TO FIX IT</div>")
            rem_html = _esc(check.remediation()).replace("\n", "<br>")
            parts.append(f"<div style='color:{c['text']};font-family:Menlo,monospace;"
                        f"font-size:11px;white-space:pre-wrap'>{rem_html}</div>")
        return "".join(parts)


def main():
    warn_if_root()
    app = QApplication(sys.argv)
    app.setApplicationName("Posture")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
