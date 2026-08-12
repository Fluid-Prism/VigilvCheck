"""window.py — the application shell.

Nav rail on the left, a top bar with the primary action, a stack of pages.
Checks is a master–detail split rather than a table, because what you do with
a gap is read why it matters and copy the fix, and that wants a pane.
"""
import html
import time
import traceback

from PySide6.QtCore import (QEasingCurve, QObject, QPropertyAnimation, QRunnable,
                            QSettings, QThreadPool, QTimer, QVariantAnimation,
                            Qt, Signal, Slot)
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
                               QScrollArea, QSplitter, QStackedWidget, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from .. import store
from ..checks import ALL_CHECKS
from ..checks.base import STATUS_FAIL, STATUS_NA, STATUS_PASS, STATUS_UNKNOWN
from ..scoring import ranked_gaps, run_all, score
from . import icons
from .theme import (MONO, PALETTES, SERIF_RICH, STATUS_LABEL, STATUS_TOKEN,
                    build_qss)
from .widgets import (ROLE_BADGE, ROLE_CHECK, ROLE_KIND, ROLE_STATUS, ROLE_SUBTITLE,
                      ROLE_TITLE, CheckDelegate, Drawer, NavRail, ScoreRing,
                      Sparkline, StatCard)

STATUSES = [STATUS_FAIL, STATUS_PASS, STATUS_UNKNOWN, STATUS_NA]
SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def esc(value):
    return html.escape(str(value)) if value is not None else ""


def esc_block(value):
    """Qt's rich text is an HTML4 subset that ignores white-space:pre-wrap, so
    preformatted remediation collapses into one paragraph without this."""
    return esc(value).replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;")


class _Signals(QObject):
    done = Signal(object)
    error = Signal(str)


class _Worker(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    @Slot()
    def run(self):
        try:
            self.signals.done.emit(self.fn())
        except Exception:
            self.signals.error.emit(traceback.format_exc().strip().splitlines()[-1])


class MainWindow(QMainWindow):
    def __init__(self, auto_scan=True):
        super().__init__()
        self.setWindowTitle("VigilvCheck")
        self.resize(1160, 750)
        self.setMinimumSize(920, 580)

        self.pool = QThreadPool.globalInstance()
        self._results = []
        self._workers = []
        self._anims = []
        self._current = None
        self._kpi_prev = {"passed": 0, "gaps": 0, "unknown": 0}

        self._settings = QSettings("Fluid-Prism", "VigilvCheck")
        saved = self._settings.value("theme")
        self.theme = saved if saved in PALETTES else self._detect_theme()
        self.c = PALETTES[self.theme]

        self._build()
        self._apply_theme(self.theme, first=True)
        self._counters = {k: self._make_counter(k) for k in self._kpi_prev}
        if auto_scan:
            self.on_scan()

    @staticmethod
    def _detect_theme():
        try:
            if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Light:
                return "light"
        except Exception:
            pass
        return "dark"

    # ── construction ─────────────────────────────────────────────────────────
    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_topbar())

        middle = QWidget()
        row = QHBoxLayout(middle)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.nav = NavRail(self.c)
        for kind, label in (("overview", "Overview"), ("findings", "Checks"),
                            ("history", "History"), ("about", "About")):
            self.nav.add_item(kind, label)
        self.nav.finish()
        self.nav.changed.connect(self._on_nav)
        row.addWidget(self.nav)

        self.stage = QWidget()
        stage_layout = QVBoxLayout(self.stage)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_overview())
        self.pages.addWidget(self._build_checks())
        self.pages.addWidget(self._build_history())
        self.pages.addWidget(self._build_about())
        stage_layout.addWidget(self.pages)
        row.addWidget(self.stage, 1)

        outer.addWidget(middle, 1)
        outer.addWidget(self._build_statusbar())

        self.drawer = Drawer(self.stage, width=290)
        self._build_drawer()

        for sequence, slot in ((QKeySequence("Ctrl+R"), self.on_scan),
                               (QKeySequence("Ctrl+F"), self._focus_search)):
            action = QAction(self)
            action.setShortcut(sequence)
            action.triggered.connect(slot)
            self.addAction(action)

    def _build_topbar(self):
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(56)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        mark = QLabel("SECURITY POSTURE")
        mark.setObjectName("BrandMark")
        name = QLabel("VigilvCheck")
        name.setObjectName("BrandName")
        brand.addWidget(mark)
        brand.addWidget(name)
        layout.addLayout(brand)

        self.progress = QLabel("")
        self.progress.setObjectName("Meta")
        layout.addSpacing(10)
        layout.addWidget(self.progress)
        layout.addStretch()

        self.btn_filter = QPushButton("  Filters")
        self.btn_filter.setObjectName("Quiet")
        self.btn_filter.setCheckable(True)
        self.btn_filter.setCursor(Qt.PointingHandCursor)
        self.btn_filter.clicked.connect(self._toggle_filters)
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("Quiet")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setToolTip("Switch theme")
        self.btn_theme.clicked.connect(self.on_theme_toggle)
        self.btn_scan = QPushButton("SCAN")
        self.btn_scan.setObjectName("Primary")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.setToolTip("Re-check this machine  (Ctrl+R)")
        self.btn_scan.clicked.connect(self.on_scan)
        for widget in (self.btn_filter, self.btn_theme, self.btn_scan):
            layout.addWidget(widget)
        return bar

    def _build_statusbar(self):
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(30)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 12, 0)
        self.status = QLabel("Ready")
        self.status.setObjectName("Meta")
        layout.addWidget(self.status)
        layout.addStretch()
        self.status_right = QLabel("")
        self.status_right.setObjectName("Meta")
        layout.addWidget(self.status_right)
        return bar

    def _page_header(self, title, subtitle):
        box = QVBoxLayout()
        box.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("PageSub")
        sub.setWordWrap(True)
        box.addWidget(title_label)
        box.addWidget(sub)
        return box

    def _panel(self, header_text):
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        head = QWidget()
        head.setObjectName("PanelHeader")
        head.setFixedHeight(36)
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(14, 0, 10, 0)
        label = QLabel(header_text)
        label.setObjectName("SectionLabel")
        head_layout.addWidget(label)
        head_layout.addStretch()
        layout.addWidget(head)
        return panel, layout, head_layout

    def _build_overview(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)
        layout.addLayout(self._page_header(
            "This machine", "Hardening basics, scored honestly, fixed one gap at a time."))

        top = QHBoxLayout()
        top.setSpacing(14)

        ring_panel = QFrame()
        ring_panel.setObjectName("Panel")
        ring_layout = QHBoxLayout(ring_panel)
        ring_layout.setContentsMargins(20, 16, 20, 16)
        ring_layout.setSpacing(18)
        self.ring = ScoreRing(self.c)
        ring_layout.addWidget(self.ring)

        ring_text = QVBoxLayout()
        ring_text.setSpacing(3)
        ring_caption = QLabel("POSTURE SCORE")
        ring_caption.setObjectName("SectionLabel")
        self.ring_count = QLabel("")
        self.ring_count.setObjectName("Meta")
        self.ring_trend = QLabel("")
        self.ring_trend.setObjectName("Meta")
        self.ring_note = QLabel("A weighted percentage of what could actually be determined.\n"
                                "It is not a verdict on whether this machine is secure.")
        self.ring_note.setObjectName("PageSub")
        self.ring_note.setWordWrap(True)
        ring_text.addWidget(ring_caption)
        ring_text.addWidget(self.ring_count)
        ring_text.addWidget(self.ring_trend)
        ring_text.addSpacing(4)
        ring_text.addWidget(self.ring_note)
        ring_text.addStretch()
        ring_layout.addLayout(ring_text, 1)
        top.addWidget(ring_panel, 3)

        cards = QVBoxLayout()
        cards.setSpacing(10)
        self.cards = {}
        for key, label in (("passed", "PASSED"), ("gaps", "GAPS"), ("unknown", "UNDETERMINED")):
            card = StatCard(label, self.c)
            self.cards[key] = card
            cards.addWidget(card)
        top.addLayout(cards, 1)
        layout.addLayout(top)

        panel, panel_layout, _ = self._panel("WHAT TO FIX FIRST")
        self.gaps_body = QLabel()
        self.gaps_body.setObjectName("Detail")
        self.gaps_body.setTextFormat(Qt.RichText)
        self.gaps_body.setWordWrap(True)
        self.gaps_body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.gaps_body.setContentsMargins(14, 12, 14, 14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.gaps_body)
        panel_layout.addWidget(scroll, 1)
        layout.addWidget(panel, 1)
        return page

    def _build_checks(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        top = QHBoxLayout()
        top.addLayout(self._page_header(
            "Checks", "Every control this tool knows how to read. Select one for the detail."))
        top.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter…  (Ctrl+F)")
        self.search.setFixedWidth(210)
        self.search.textChanged.connect(self._render_tree)
        top.addWidget(self.search, 0, Qt.AlignBottom)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        left = QFrame()
        left.setObjectName("Panel")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(0)
        self.tree.setMouseTracking(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setVerticalScrollMode(QTreeWidget.ScrollPerPixel)
        self.delegate = CheckDelegate(self.c, self.tree)
        self.tree.setItemDelegate(self.delegate)
        self.tree.currentItemChanged.connect(self._on_select)
        left_layout.addWidget(self.tree)
        splitter.addWidget(left)

        right = QFrame()
        right.setObjectName("Panel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        head = QWidget()
        head.setObjectName("PanelHeader")
        head.setFixedHeight(36)
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(14, 0, 8, 0)
        self.detail_label = QLabel("DETAIL")
        self.detail_label.setObjectName("SectionLabel")
        head_layout.addWidget(self.detail_label)
        head_layout.addStretch()
        self.btn_copy = QPushButton("Copy fix")
        self.btn_copy.setObjectName("Quiet")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy_fix)
        head_layout.addWidget(self.btn_copy)
        right_layout.addWidget(head)

        self.detail = QLabel()
        self.detail.setObjectName("Detail")
        self.detail.setTextFormat(Qt.RichText)
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail.setContentsMargins(16, 14, 16, 16)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(self.detail)
        right_layout.addWidget(detail_scroll, 1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([460, 540])
        layout.addWidget(splitter, 1)
        return page

    def _build_history(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)
        layout.addLayout(self._page_header(
            "History", "Every scan recorded on this machine, kept locally."))

        panel, panel_layout, _ = self._panel("SCORE OVER TIME")
        self.spark = Sparkline(self.c)
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(10, 10, 10, 4)
        wrapper_layout.addWidget(self.spark)
        panel_layout.addWidget(wrapper)
        layout.addWidget(panel)

        list_panel, list_layout, _ = self._panel("SCANS")
        self.history_body = QLabel()
        self.history_body.setObjectName("Detail")
        self.history_body.setTextFormat(Qt.RichText)
        self.history_body.setWordWrap(True)
        self.history_body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.history_body.setContentsMargins(14, 12, 14, 14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.history_body)
        list_layout.addWidget(scroll, 1)
        layout.addWidget(list_panel, 1)
        return page

    def _build_about(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(16)
        layout.addLayout(self._page_header(
            "About", "What this tool checks, and what the score does and doesn't mean."))
        panel = QFrame()
        panel.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        self.about_body = QLabel()
        self.about_body.setObjectName("Detail")
        self.about_body.setTextFormat(Qt.RichText)
        self.about_body.setWordWrap(True)
        self.about_body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.about_body.setContentsMargins(18, 16, 18, 18)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.about_body)
        panel_layout.addWidget(scroll)
        layout.addWidget(panel, 1)
        return page

    def _build_drawer(self):
        close = QPushButton()
        close.setObjectName("Quiet")
        close.setCursor(Qt.PointingHandCursor)
        close.setFixedWidth(30)
        close.clicked.connect(self.drawer.close_drawer)
        self._drawer_close = close
        self.drawer.add_header_button(close)
        self.drawer.closed.connect(lambda: self.btn_filter.setChecked(False))

        body = self.drawer.body_layout
        label = QLabel("STATUS")
        label.setObjectName("SectionLabel")
        body.addWidget(label)
        self.status_boxes = {}
        for status in STATUSES:
            box = QCheckBox(STATUS_LABEL[status].title() if status != STATUS_NA else "Not applicable")
            box.setChecked(status != STATUS_NA)
            box.stateChanged.connect(self._render_tree)
            self.status_boxes[status] = box
            body.addWidget(box)

        body.addSpacing(10)
        sev_label = QLabel("SEVERITY")
        sev_label.setObjectName("SectionLabel")
        body.addWidget(sev_label)
        self.severity_boxes = {}
        for severity in SEVERITY_ORDER:
            box = QCheckBox(severity.capitalize())
            box.setChecked(True)
            box.stateChanged.connect(self._render_tree)
            self.severity_boxes[severity] = box
            body.addWidget(box)

        body.addStretch()
        self.filter_summary = QLabel("")
        self.filter_summary.setObjectName("Meta")
        self.filter_summary.setWordWrap(True)
        body.addWidget(self.filter_summary)
        reset = QPushButton("Reset filters")
        reset.clicked.connect(self._reset_filters)
        body.addWidget(reset)

    # ── theme ────────────────────────────────────────────────────────────────
    def on_theme_toggle(self):
        new_theme = "light" if self.theme == "dark" else "dark"
        root = self.centralWidget()
        self._fade(root, 1.0, 0.0, 100)
        QTimer.singleShot(62, lambda: self._apply_theme(new_theme))
        QTimer.singleShot(104, lambda: self._fade(root, 0.0, 1.0, 150))

    def _apply_theme(self, name, first=False):
        self.theme = name
        self.c = PALETTES[name]
        self._settings.setValue("theme", name)
        self.setStyleSheet(build_qss(self.c))
        self.nav.set_palette(self.c)
        self.delegate.set_palette(self.c)
        self.ring.set_palette(self.c)
        self.spark.set_palette(self.c)
        self.cards["passed"].set_colour(self.c["pass"])
        self.cards["gaps"].set_colour(self.c["fail"])
        self.cards["unknown"].set_colour(self.c["unknown"])
        self.btn_theme.setIcon(icons.icon("sun" if self.c["is_dark"] else "moon",
                                          self.c["text_muted"], 16))
        self.btn_filter.setIcon(icons.icon("filter", self.c["text_muted"], 15))
        self.btn_scan.setIcon(icons.icon("scan", self.c["accent_ink"], 14))
        self._drawer_close.setIcon(icons.icon("close", self.c["text_muted"], 14))
        self.btn_copy.setIcon(icons.icon("copy", self.c["text_muted"], 14))
        self._render_about()
        if not first:
            self.tree.viewport().update()
            if self._current:
                self._render_detail(*self._current)
            self._render_history()
            if self._results:
                self._render_overview()

    def _fade(self, widget, start, end, duration):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anims.append(anim)

        def cleanup():
            if anim in self._anims:
                self._anims.remove(anim)
            widget.setGraphicsEffect(None)

        anim.finished.connect(cleanup)
        anim.start()

    def _make_counter(self, key):
        anim = QVariantAnimation(self)
        anim.setDuration(520)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.valueChanged.connect(
            lambda value, k=key: self.cards[k].value.setText(str(int(value))))
        return anim

    def _count_to(self, key, value):
        anim = self._counters[key]
        anim.stop()
        anim.setStartValue(self._kpi_prev.get(key, 0))
        anim.setEndValue(value)
        anim.start()
        self._kpi_prev[key] = value

    # ── navigation ───────────────────────────────────────────────────────────
    def _on_nav(self, index):
        self.pages.setCurrentIndex(index)
        self._fade(self.pages.currentWidget(), 0.0, 1.0, 170)
        if index == 2:
            self._render_history()

    def _toggle_filters(self):
        if self.pages.currentIndex() != 1:
            self.nav.select(1)
        self.drawer.toggle("FILTERS")
        self.btn_filter.setChecked(self.drawer.is_open)

    def _reset_filters(self):
        for status, box in self.status_boxes.items():
            box.setChecked(status != STATUS_NA)
        for box in self.severity_boxes.values():
            box.setChecked(True)
        self.search.clear()

    def _focus_search(self):
        if self.pages.currentIndex() != 1:
            self.nav.select(1)
        self.search.setFocus()
        self.search.selectAll()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.drawer.reposition()

    # ── scanning ─────────────────────────────────────────────────────────────
    def on_scan(self):
        if not self.btn_scan.isEnabled():
            return
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("CHECKING")
        self.status.setText("Reading this machine's settings…")
        self._pulse_step = 0
        self._pulse()

        worker = _Worker(self._scan_and_record)
        self._workers.append(worker)

        def cleanup(*_):
            if worker in self._workers:
                self._workers.remove(worker)

        worker.signals.done.connect(self._on_data)
        worker.signals.done.connect(cleanup)
        worker.signals.error.connect(self._on_error)
        worker.signals.error.connect(cleanup)
        self.pool.start(worker)

    def _pulse(self):
        if self.btn_scan.isEnabled():
            self.progress.setText("")
            return
        self._pulse_step = (self._pulse_step + 1) % 4
        self.progress.setText("checking" + "." * self._pulse_step)
        QTimer.singleShot(320, self._pulse)

    @staticmethod
    def _scan_and_record():
        results = run_all(ALL_CHECKS)
        value, applicable = score(results)
        store.record_scan(results, value, applicable)
        return results

    @Slot(object)
    def _on_data(self, results):
        self._results = results
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("SCAN")
        self.progress.setText("")
        self._render_overview()
        self._render_tree()
        self._render_history()

        passed = sum(1 for _, r in results if r.status == STATUS_PASS)
        failed = sum(1 for _, r in results if r.status == STATUS_FAIL)
        undetermined = sum(1 for _, r in results if r.status in (STATUS_UNKNOWN, STATUS_NA))
        self.status.setText(f"{passed} passed · {failed} gap(s) · {undetermined} undetermined")
        self.status_right.setText(time.strftime("checked %H:%M:%S"))

    @Slot(str)
    def _on_error(self, message):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("SCAN")
        self.progress.setText("")
        self.status.setText(f"Error: {message}")

    # ── rendering ────────────────────────────────────────────────────────────
    def _render_overview(self):
        c = self.c
        results = self._results
        value, applicable = score(results)
        self.ring.set_score(value, applicable, len(results))
        self.ring_count.setText(f"{applicable} of {len(results)} checks determinable")

        self._count_to("passed", sum(1 for _, r in results if r.status == STATUS_PASS))
        self._count_to("gaps", sum(1 for _, r in results if r.status == STATUS_FAIL))
        self._count_to("unknown", sum(1 for _, r in results
                                      if r.status in (STATUS_UNKNOWN, STATUS_NA)))

        history = store.score_history(limit=30)
        scored = [(ts, s) for ts, s, _ in history if s is not None]
        if len(scored) >= 2:
            delta = scored[0][1] - scored[1][1]
            if delta > 0:
                self.ring_trend.setText(f"▲ +{delta} since the last scan")
                self.ring_trend.setStyleSheet(f"color:{c['pass']}; background:transparent;")
            elif delta < 0:
                self.ring_trend.setText(f"▼ {delta} since the last scan")
                self.ring_trend.setStyleSheet(f"color:{c['fail']}; background:transparent;")
            else:
                self.ring_trend.setText("No change since the last scan")
                self.ring_trend.setStyleSheet(f"color:{c['text_faint']}; background:transparent;")
        else:
            self.ring_trend.setText("First recorded scan")
            self.ring_trend.setStyleSheet(f"color:{c['text_faint']}; background:transparent;")

        gaps = ranked_gaps(results)
        if not gaps:
            self.gaps_body.setText(
                f"<div style='color:{c['text_muted']};padding:14px 2px'>No gaps in what could "
                "be checked. That is not the same as secure — see About for what this covers."
                "</div>")
            return
        rows = []
        for check, result in gaps:
            rows.append(
                f"<tr>"
                f"<td width='72' style='padding:7px 10px 7px 0;font-family:{MONO};font-size:10px;"
                f"color:{c[check.severity]};vertical-align:top'>{esc(check.severity.upper())}</td>"
                f"<td style='padding:7px 0'>"
                f"<span style='color:{c['text']};font-size:13px'>{esc(check.title)}</span><br>"
                f"<span style='color:{c['text_muted']};font-size:11px'>{esc(result.detail)}</span>"
                f"</td></tr>"
                f"<tr><td colspan='2' style='background:{c['border']};font-size:1px'></td></tr>")
        self.gaps_body.setText(
            f"<table width='100%' cellspacing='0' cellpadding='0'>{''.join(rows)}</table>")

    def _passes_filters(self, check, result, query):
        if not self.status_boxes[result.status].isChecked():
            return False
        if not self.severity_boxes.get(check.severity, self.status_boxes[STATUS_PASS]).isChecked():
            return False
        if query and query not in check.title.lower() and query not in result.detail.lower():
            return False
        return True

    def _render_tree(self):
        if not self._results:
            return
        query = self.search.text().lower().strip()
        kept = [(c, r) for c, r in self._results if self._passes_filters(c, r, query)]
        order = {STATUS_FAIL: 0, STATUS_UNKNOWN: 1, STATUS_PASS: 2, STATUS_NA: 3}
        kept.sort(key=lambda cr: (order.get(cr[1].status, 9),
                                  SEVERITY_ORDER.index(cr[0].severity)
                                  if cr[0].severity in SEVERITY_ORDER else 9))

        self.tree.clear()
        current_group = None
        group_item = None
        for check, result in kept:
            label = {STATUS_FAIL: "NEEDS ATTENTION", STATUS_UNKNOWN: "COULDN'T DETERMINE",
                     STATUS_PASS: "PASSING", STATUS_NA: "NOT APPLICABLE"}[result.status]
            if label != current_group:
                current_group = label
                group_item = QTreeWidgetItem(self.tree)
                group_item.setData(0, ROLE_KIND, "group")
                group_item.setData(0, ROLE_TITLE, label)
                group_item.setData(0, ROLE_BADGE,
                                   str(sum(1 for _, r in kept if r.status == result.status)))
                group_item.setFlags(Qt.ItemIsEnabled)
                group_item.setExpanded(True)
            item = QTreeWidgetItem(group_item)
            item.setData(0, ROLE_KIND, "check")
            item.setData(0, ROLE_CHECK, (check, result))
            item.setData(0, ROLE_TITLE, check.title)
            item.setData(0, ROLE_SUBTITLE, result.detail)
            item.setData(0, ROLE_STATUS, result.status)

        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setExpanded(True)

        self.filter_summary.setText(f"Showing {len(kept)} of {len(self._results)} checks.")
        self.status_right.setText(f"{len(kept)} of {len(self._results)} shown")

    def _on_select(self, current, _previous):
        if current is None or current.data(0, ROLE_KIND) != "check":
            return
        check, result = current.data(0, ROLE_CHECK)
        self._current = (check, result)
        self._render_detail(check, result)
        self.btn_copy.setEnabled(result.status == STATUS_FAIL)

    def _render_detail(self, check, result):
        c = self.c
        token = STATUS_TOKEN.get(result.status, "na")
        self.detail_label.setText(f"{STATUS_LABEL.get(result.status, '')} · "
                                  f"{check.severity.upper()}")
        parts = [
            f"<div style='font-family:{SERIF_RICH};font-size:18px;font-weight:600;"
            f"color:{c['text']}'>{esc(check.title)}</div>",
            f"<div style='font-family:{MONO};font-size:10px;color:{c['text_faint']};"
            f"margin:6px 0 14px 0'>{esc(check.cis_topic)}</div>",
            f"<div style='padding:11px 13px;background:{c[token + '_wash']};"
            f"border-left:3px solid {c[token]};color:{c['text']};font-size:12px'>"
            f"{esc(result.detail)}</div>",
            f"<div style='margin-top:18px;color:{c['accent']};font-family:{MONO};font-size:10px;"
            f"font-weight:700;letter-spacing:1.5px'>WHY IT MATTERS</div>",
            f"<div style='margin-top:6px;color:{c['text_muted']};line-height:150%'>"
            f"{esc(check.rationale)}</div>",
        ]
        if result.status == STATUS_FAIL:
            parts += [
                f"<div style='margin-top:18px;color:{c['accent']};font-family:{MONO};"
                f"font-size:10px;font-weight:700;letter-spacing:1.5px'>HOW TO FIX IT</div>",
                f"<div style='margin-top:8px;padding:12px 13px;background:{c['surface_alt']};"
                f"border:1px solid {c['border']};color:{c['text']};font-family:{MONO};"
                f"font-size:11px;line-height:145%'>{esc_block(check.remediation())}</div>",
            ]
        elif result.status == STATUS_UNKNOWN:
            parts.append(
                f"<div style='margin-top:18px;color:{c['text_muted']};font-size:12px;"
                f"line-height:150%'>This one couldn't be determined, so it is left out of the "
                f"score entirely — not counted as passing, and not held against you either.</div>")
        self.detail.setText("".join(parts))

    def _copy_fix(self):
        if not self._current:
            return
        QApplication.clipboard().setText(self._current[0].remediation())
        self.status.setText("Fix copied to clipboard.")

    def _render_history(self):
        c = self.c
        history = store.score_history(limit=40)
        self.spark.set_data(history)
        if not history:
            self.history_body.setText(
                f"<div style='color:{c['text_muted']};padding:12px 2px'>No scans recorded yet.</div>")
            return
        rows = []
        for index, (ts, value, applicable) in enumerate(history):
            when = time.strftime("%d %b %Y · %H:%M", time.localtime(ts))
            shown = f"{value}/100" if value is not None else "—"
            delta = ""
            if index + 1 < len(history) and value is not None and history[index + 1][1] is not None:
                change = value - history[index + 1][1]
                if change > 0:
                    delta = f"<span style='color:{c['pass']}'>▲ +{change}</span>"
                elif change < 0:
                    delta = f"<span style='color:{c['fail']}'>▼ {change}</span>"
                else:
                    delta = f"<span style='color:{c['text_faint']}'>no change</span>"
            rows.append(
                f"<div style='padding:8px 0;border-bottom:1px solid {c['border']}'>"
                f"<span style='font-family:{MONO};font-size:11px;color:{c['text']}'>{esc(when)}"
                f"</span> &nbsp; <span style='color:{c['text_muted']}'>{esc(shown)}</span>"
                f" &nbsp; <span style='color:{c['text_faint']};font-size:11px'>"
                f"({applicable} of {len(ALL_CHECKS)} determinable)</span> &nbsp; {delta}</div>")
        self.history_body.setText("".join(rows))

    def _render_about(self):
        c = self.c
        rows = "".join(
            f"<tr><td style='padding:3px 14px 3px 0;font-family:{MONO};font-size:10px;"
            f"color:{c[check.severity]};vertical-align:top'>{esc(check.severity)}</td>"
            f"<td style='padding:3px 0;color:{c['text_muted']}'>{esc(check.title)}</td></tr>"
            for check in sorted(ALL_CHECKS, key=lambda ch: SEVERITY_ORDER.index(ch.severity)))
        self.about_body.setText(f"""
<div style='font-family:{SERIF_RICH};font-size:17px;font-weight:600;color:{c['text']}'>VigilvCheck</div>
<div style='color:{c['text_muted']};margin-top:6px;line-height:150%'>
Checks this machine against a set of well-known hardening basics, scores what it can actually
determine, and explains each gap in plain English with a copy-paste fix.</div>

<div style='margin-top:20px;color:{c['accent']};font-family:{MONO};font-size:10px;
font-weight:700;letter-spacing:1.5px'>WHAT THE SCORE MEANS</div>
<div style='margin-top:6px;color:{c['text_muted']};line-height:150%'>
A severity-weighted percentage of the checks that passed. A 100 means every check this tool
knows how to run passed — it does not mean this machine is secure. It checks {len(ALL_CHECKS)}
specific things, and not your passwords, your browser extensions, or whether you click links
in phishing mail.</div>

<div style='margin-top:18px;color:{c['accent']};font-family:{MONO};font-size:10px;
font-weight:700;letter-spacing:1.5px'>UNDETERMINED IS NOT A FAILURE</div>
<div style='margin-top:6px;color:{c['text_muted']};line-height:150%'>
Checks that need administrator access, or a desktop environment this doesn't know how to read,
are excluded from the score entirely — not counted as passing, not held against you. That is
the tool being honest about the limits of what it can see, not a hidden fail.</div>

<div style='margin-top:18px;color:{c['accent']};font-family:{MONO};font-size:10px;
font-weight:700;letter-spacing:1.5px'>IT CHANGES NOTHING</div>
<div style='margin-top:6px;color:{c['text_muted']};line-height:150%'>
Every read is local and read-only. No fix is ever applied for you — see the README for why
that is a deliberate line rather than a missing feature.</div>

<div style='margin-top:22px;color:{c['text_faint']};font-family:{MONO};font-size:10px;
font-weight:700;letter-spacing:1.5px'>CHECKS ({len(ALL_CHECKS)})</div>
<table style='margin-top:8px'>{rows}</table>
""")
