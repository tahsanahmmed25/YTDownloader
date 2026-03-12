style = """
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #edf2f8, stop:1 #dce6f2);
    font-family: "Segoe UI Variable", "Segoe UI";
}

QWidget {
    color: #1f2a36;
    font-size: 13px;
}

QPushButton {
    qproperty-cursor: pointingHandCursor;
}

QToolButton {
    qproperty-cursor: pointingHandCursor;
}

QFrame#Sidebar {
    background: rgba(253, 253, 254, 210);
    border: 1px solid rgba(31, 42, 54, 20);
    border-radius: 18px;
}

QLabel#Brand {
    font-size: 20px;
    font-weight: 600;
    padding: 6px 4px;
}

QPushButton#NavButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 12px;
    padding: 10px 14px;
    text-align: left;
    color: #1f2a36;
    qproperty-cursor: arrowCursor;
}

QPushButton#NavButton:focus {
    outline: none;
    border: 1px solid transparent;
}

QPushButton#NavButton:focus:checked {
    border: 1px solid rgba(79, 141, 255, 0.5);
}

QPushButton#NavButton:hover {
    background: rgba(0, 0, 0, 0.05);
}

QPushButton#NavButton:checked {
    background: rgba(79, 141, 255, 0.18);
    border: 1px solid rgba(79, 141, 255, 0.5);
}

QPushButton#NavButton[activeDownloads="true"] {
    background: #6fa7ff;
    border: 1px solid rgba(79, 141, 255, 0.7);
    color: #ffffff;
}

QPushButton#NavButton[activeDownloads="true"]:hover {
    background: #7cb2ff;
}

QFrame#Card {
    background: rgba(253, 253, 254, 0.88);
    border: 1px solid rgba(31, 42, 54, 24);
    border-radius: 16px;
}

QFrame#LibraryCard {
    background: rgba(253, 253, 254, 0.88);
    border: 1px solid rgba(31, 42, 54, 24);
    border-radius: 14px;
}

QLabel#SectionTitle {
    font-size: 16px;
    font-weight: 600;
    color: #1a2330;
}

QLabel#CardTitle {
    font-size: 14px;
    font-weight: 600;
}

QLabel#InfoTitle {
    font-size: 15px;
    font-weight: 600;
}

QLabel#LibraryTitle {
    font-size: 14px;
    font-weight: 600;
}

QLabel#MutedText {
    color: #6e7b88;
}

QLineEdit#UrlInput {
    background: rgba(253, 253, 254, 0.9);
    border: 1px solid rgba(31, 42, 54, 40);
    border-radius: 14px;
    padding: 10px 12px;
    font-size: 14px;
    color: #1f2a36;
}

QLineEdit {
    background: rgba(253, 253, 254, 0.9);
    border: 1px solid rgba(31, 42, 54, 40);
    border-radius: 10px;
    padding: 6px 10px;
    color: #1f2a36;
}

QSpinBox {
    background: rgba(253, 253, 254, 0.9);
    border: 1px solid rgba(31, 42, 54, 40);
    border-radius: 10px;
    padding: 4px 8px;
    color: #1f2a36;
}

QPushButton#PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    color: #ffffff;
    border: none;
    border-radius: 14px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6ba0ff, stop:1 #38d6cd);
}

QPushButton#GhostButton {
    background: rgba(253, 253, 254, 0.85);
    border: 1px solid rgba(31, 42, 54, 30);
    border-radius: 10px;
    padding: 6px 12px;
    color: #1f2a36;
}

QPushButton#GhostButton:hover {
    background: rgba(79, 141, 255, 0.12);
    border: 1px solid rgba(79, 141, 255, 0.45);
}

QComboBox {
    background: rgba(253, 253, 254, 0.9);
    border: 1px solid rgba(31, 42, 54, 40);
    border-radius: 10px;
    padding: 6px 10px;
    color: #1f2a36;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox::down-arrow {
    image: url(:/qt-project.org/styles/commonstyle/images/arrowdown-16.png);
    width: 10px;
    height: 10px;
}

QComboBox QAbstractItemView {
    background: #f7f9fc;
    border: 1px solid rgba(31, 42, 54, 0.2);
    selection-background-color: rgba(79, 141, 255, 0.2);
    color: #1f2a36;
}

QCheckBox {
    spacing: 8px;
}

QProgressBar {
    background: rgba(253, 253, 254, 0.9);
    border: 1px solid rgba(31, 42, 54, 40);
    border-radius: 10px;
    text-align: center;
    height: 18px;
    color: #1f2a36;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border-radius: 10px;
}

QProgressBar#FetchBar {
    background: rgba(79, 141, 255, 0.2);
    border: none;
    height: 4px;
    border-radius: 2px;
}

QProgressBar#FetchBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border-radius: 2px;
}

QToolButton#ThumbButton {
    border: none;
    background: transparent;
}

QToolButton#ThumbButton:hover {
    background: rgba(79, 141, 255, 0.12);
    border-radius: 10px;
}

QScrollArea#GlassScroll {
    background: transparent;
    border: none;
}

QScrollArea#GlassScroll QAbstractScrollArea::viewport {
    background: transparent;
}

QScrollArea#GlassScroll QWidget {
    background: transparent;
}

QWidget#Page {
    background: transparent;
}

QScrollArea#GlassScroll QAbstractScrollArea::viewport {
    background: transparent;
}

QScrollArea#GlassScroll QWidget {
    background: transparent;
}

QWidget#Page {
    background: transparent;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 5px;
    border: 1px solid rgba(31, 42, 54, 0.45);
    background: #fdfdfe;
}

QCheckBox::indicator:hover {
    border: 1px solid rgba(79, 141, 255, 0.8);
}

QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border: 1px solid rgba(79, 141, 255, 0.8);
}

QCheckBox#PlaylistToggle {
    spacing: 6px;
    font-weight: 600;
}

QCheckBox#PlaylistToggle::indicator {
    width: 40px;
    height: 20px;
    border-radius: 10px;
    border: 1px solid rgba(31, 42, 54, 0.35);
    background: rgba(200, 208, 220, 0.9);
}

QCheckBox#PlaylistToggle::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border: 1px solid rgba(79, 141, 255, 0.8);
}

QToolButton#PasteButton {
    background: #fdfdfe;
    border: 1px solid rgba(31, 42, 54, 0.4);
    border-radius: 12px;
    padding: 8px 12px;
    font-weight: 600;
    color: #1f2a36;
}

QToolButton#PasteButton:hover {
    background: rgba(79, 141, 255, 0.15);
    border: 1px solid rgba(79, 141, 255, 0.6);
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: rgba(31, 42, 54, 0.18);
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QFrame#Toast {
    background: rgba(253, 253, 254, 0.96);
    border: 1px solid rgba(31, 42, 54, 0.2);
    border-radius: 12px;
}

QFrame#Toast[variant="warning"] {
    background: rgba(255, 244, 235, 0.96);
    border: 1px solid rgba(243, 156, 18, 0.6);
}

QLabel#ToastLabel {
    color: #1f2a36;
    font-size: 13px;
    font-weight: 600;
}

QLabel#StatusIcon {
    font-size: 14px;
    font-weight: 700;
}

QLabel#StatusIcon[status="done"] {
    color: #2ecc71;
}

QLabel#StatusIcon[status="failed"] {
    color: #e74c3c;
}

QLabel#StatusIcon[status="active"] {
    color: #4f8dff;
}
"""

dark_style = """
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #2b3444, stop:1 #202838);
    font-family: "Segoe UI Variable", "Segoe UI";
}

QWidget {
    color: #e6edf3;
    font-size: 13px;
}

QPushButton {
    qproperty-cursor: pointingHandCursor;
}

QToolButton {
    qproperty-cursor: pointingHandCursor;
}

QFrame#Sidebar {
    background: rgba(38, 46, 60, 0.9);
    border: 1px solid rgba(230, 237, 243, 36);
    border-radius: 18px;
}

QLabel#Brand {
    font-size: 20px;
    font-weight: 600;
    padding: 6px 4px;
}

QPushButton#NavButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 12px;
    padding: 10px 14px;
    text-align: left;
    color: #e6edf3;
    qproperty-cursor: arrowCursor;
}

QPushButton#NavButton:focus {
    outline: none;
    border: 1px solid transparent;
}

QPushButton#NavButton:focus:checked {
    border: 1px solid rgba(79, 141, 255, 0.5);
}

QPushButton#NavButton:hover {
    background: rgba(255, 255, 255, 0.06);
}

QPushButton#NavButton:checked {
    background: rgba(79, 141, 255, 0.18);
    border: 1px solid rgba(79, 141, 255, 0.5);
}

QPushButton#NavButton[activeDownloads="true"] {
    background: #5b94ff;
    border: 1px solid rgba(79, 141, 255, 0.7);
    color: #ffffff;
}

QPushButton#NavButton[activeDownloads="true"]:hover {
    background: #69a0ff;
}

QFrame#Card, QFrame#LibraryCard {
    background: rgba(36, 45, 60, 0.88);
    border: 1px solid rgba(230, 237, 243, 24);
    border-radius: 16px;
}

QScrollArea#GlassScroll QAbstractScrollArea::viewport {
    background: transparent;
}

QScrollArea#GlassScroll QWidget {
    background: transparent;
}

QWidget#Page {
    background: transparent;
}

QLabel#SectionTitle {
    font-size: 16px;
    font-weight: 600;
    color: #f2f6fb;
}

QLabel#CardTitle,
QLabel#InfoTitle,
QLabel#LibraryTitle {
    font-weight: 600;
}

QLabel#MutedText {
    color: #9aa7b4;
}

QLineEdit#UrlInput {
    background: rgba(34, 43, 58, 0.95);
    border: 1px solid rgba(230, 237, 243, 40);
    border-radius: 14px;
    padding: 10px 12px;
    font-size: 14px;
    color: #e6edf3;
}

QLineEdit, QComboBox {
    background: rgba(34, 43, 58, 0.92);
    border: 1px solid rgba(230, 237, 243, 40);
    border-radius: 10px;
    padding: 6px 10px;
    color: #e6edf3;
}

QSpinBox {
    background: rgba(34, 43, 58, 0.92);
    border: 1px solid rgba(230, 237, 243, 40);
    border-radius: 10px;
    padding: 4px 8px;
    color: #e6edf3;
}

QPushButton#PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    color: #ffffff;
    border: none;
    border-radius: 14px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6ba0ff, stop:1 #38d6cd);
}

QPushButton#GhostButton {
    background: rgba(25, 32, 45, 0.85);
    border: 1px solid rgba(230, 237, 243, 35);
    border-radius: 10px;
    padding: 6px 12px;
    color: #e6edf3;
}

QPushButton#GhostButton:hover {
    background: rgba(79, 141, 255, 0.18);
    border: 1px solid rgba(79, 141, 255, 0.55);
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox::down-arrow {
    image: url(:/qt-project.org/styles/commonstyle/images/arrowdown-16.png);
    width: 10px;
    height: 10px;
}

QComboBox QAbstractItemView {
    background: #273244;
    border: 1px solid rgba(230, 237, 243, 0.2);
    selection-background-color: rgba(79, 141, 255, 0.2);
    color: #e6edf3;
}

QProgressBar {
    background: rgba(34, 43, 58, 0.9);
    border: 1px solid rgba(230, 237, 243, 40);
    border-radius: 10px;
    text-align: center;
    height: 18px;
    color: #e6edf3;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border-radius: 10px;
}

QProgressBar#FetchBar {
    background: rgba(79, 141, 255, 0.18);
    border: none;
    height: 4px;
    border-radius: 2px;
}

QProgressBar#FetchBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border-radius: 2px;
}

QToolButton#ThumbButton {
    border: none;
    background: transparent;
}

QToolButton#ThumbButton:hover {
    background: rgba(79, 141, 255, 0.2);
    border-radius: 10px;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 5px;
    border: 1px solid rgba(230, 237, 243, 0.45);
    background: rgba(34, 43, 58, 0.9);
}

QCheckBox::indicator:hover {
    border: 1px solid rgba(79, 141, 255, 0.8);
}

QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border: 1px solid rgba(79, 141, 255, 0.8);
}

QCheckBox#PlaylistToggle {
    spacing: 6px;
    font-weight: 600;
}

QCheckBox#PlaylistToggle::indicator {
    width: 40px;
    height: 20px;
    border-radius: 10px;
    border: 1px solid rgba(230, 237, 243, 0.45);
    background: rgba(70, 80, 96, 0.9);
}

QCheckBox#PlaylistToggle::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border: 1px solid rgba(79, 141, 255, 0.8);
}

QToolButton#PasteButton {
    background: rgba(34, 43, 58, 0.9);
    border: 1px solid rgba(230, 237, 243, 0.4);
    border-radius: 12px;
    padding: 8px 12px;
    font-weight: 600;
    color: #e6edf3;
}

QToolButton#PasteButton:hover {
    background: rgba(79, 141, 255, 0.25);
    border: 1px solid rgba(79, 141, 255, 0.6);
}

QScrollArea#GlassScroll {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: rgba(230, 237, 243, 0.18);
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QFrame#Toast {
    background: rgba(44, 53, 68, 0.96);
    border: 1px solid rgba(230, 237, 243, 0.3);
    border-radius: 12px;
}

QFrame#Toast[variant="warning"] {
    background: rgba(74, 58, 36, 0.96);
    border: 1px solid rgba(243, 156, 18, 0.6);
}

QLabel#ToastLabel {
    color: #e6edf3;
    font-size: 13px;
    font-weight: 600;
}

QLabel#StatusIcon {
    font-size: 14px;
    font-weight: 700;
}

QLabel#StatusIcon[status="done"] {
    color: #2ecc71;
}

QLabel#StatusIcon[status="failed"] {
    color: #e74c3c;
}

QLabel#StatusIcon[status="active"] {
    color: #4f8dff;
}
"""
