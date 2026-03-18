style = """
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #edf2f8, stop:1 #dce6f2);
    font-family: "Google Sans", "Segoe UI Variable", "Segoe UI";
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
    border: 1px solid transparent;
}

QPushButton#NavButton:hover {
    background: rgba(0, 0, 0, 0.05);
}

QPushButton#NavButton:checked {
    background: rgba(79, 141, 255, 0.18);
    border: 1px solid rgba(79, 141, 255, 0.5);
}

QPushButton#NavButton[activeDownloads="true"] {
    background: transparent;
    border: 2px solid rgba(79, 141, 255, 0.72);
    color: #1f2a36;
}

QPushButton#NavButton[activeDownloads="true"]:hover {
    background: rgba(79, 141, 255, 0.08);
}

QPushButton#NavButton[pulse="true"] {
    background: rgba(79, 141, 255, 0.16);
    border: 1px solid rgba(79, 141, 255, 0.78);
}

QFrame#Card {
    background: rgba(253, 253, 254, 0.88);
    border: 1px solid rgba(31, 42, 54, 24);
    border-radius: 16px;
}

QFrame#OptionsCard {
    background: #f4f5f7;
    border: 1px solid rgba(31, 42, 54, 24);
    border-radius: 16px;
}

QDialog, QMessageBox {
    background: #fdfdfe;
    color: #1f2a36;
}

QDialog QLabel, QMessageBox QLabel {
    color: #1f2a36;
}

QDialog QTextEdit, QMessageBox QTextEdit {
    background: #ffffff;
    color: #1f2a36;
    border: 1px solid rgba(31, 42, 54, 0.2);
    border-radius: 8px;
}

QDialogButtonBox QPushButton, QMessageBox QPushButton {
    background: rgba(253, 253, 254, 0.92);
    border: 1px solid rgba(31, 42, 54, 0.2);
    border-radius: 10px;
    padding: 6px 12px;
    color: #1f2a36;
}

QDialogButtonBox QPushButton:hover, QMessageBox QPushButton:hover {
    background: rgba(79, 141, 255, 0.12);
    border: 1px solid rgba(79, 141, 255, 0.45);
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
    font-size: 14px;
    font-weight: 600;
}

QLabel#InfoSubtle {
    color: #2f3a47;
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

QPushButton#PrimaryButton:disabled {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(79, 141, 255, 0.55), stop:1 rgba(42, 201, 194, 0.55));
    color: rgba(255, 255, 255, 0.85);
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

QPushButton#GhostButton:disabled {
    background: rgba(253, 253, 254, 0.65);
    border: 1px solid rgba(31, 42, 54, 0.2);
    color: rgba(31, 42, 54, 0.55);
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
    selection-background-color: rgba(79, 141, 255, 0.22);
    selection-color: #1f2a36;
    color: #1f2a36;
}

QComboBox QAbstractItemView::item {
    background: transparent;
    color: #1f2a36;
}

QListView#ComboPopupView {
    background: #f7f9fc;
    border: 1px solid rgba(31, 42, 54, 0.2);
    color: #1f2a36;
    selection-background-color: rgba(79, 141, 255, 0.22);
    selection-color: #1f2a36;
}

QListView#ComboPopupView::item {
    padding: 6px 10px;
}

QAbstractItemView, QAbstractItemView::item {
    background: #f7f9fc;
    color: #1f2a36;
    selection-background-color: rgba(79, 141, 255, 0.22);
    selection-color: #1f2a36;
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
    padding: 2px;
    color: #1f2a36;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border-radius: 8px;
}

QProgressBar#FetchBar {
    background: rgba(79, 141, 255, 0.2);
    border: none;
    height: 4px;
    padding: 0px;
    border-radius: 2px;
}

QProgressBar#FetchBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border-radius: 2px;
}

QProgressBar#LibraryNavPulse {
    background: rgba(79, 141, 255, 0.22);
    border: none;
    border-radius: 2px;
    margin-left: 8px;
    margin-right: 8px;
}

QProgressBar#LibraryNavPulse::chunk {
    background: #6ea3ff;
    border-radius: 2px;
}

QToolButton#ThumbButton {
    border: none;
    background: transparent;
    padding: 0px;
    margin: 0px;
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

QScrollArea#CookiesScroll {
    background: transparent;
    border: none;
}

QScrollArea#CookiesScroll QAbstractScrollArea::viewport {
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

QScrollArea#CookiesScroll {
    background: transparent;
    border: none;
}

QScrollArea#CookiesScroll QAbstractScrollArea::viewport {
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

QCheckBox#ThumbToggle {
    spacing: 8px;
    font-weight: 500;
    color: #2b3744;
}

QCheckBox#ThumbToggle::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid rgba(31, 42, 54, 0.42);
    background: #fdfdfe;
}

QCheckBox#ThumbToggle::indicator:hover {
    border: 1px solid rgba(79, 141, 255, 0.78);
}

QCheckBox#ThumbToggle::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border: 1px solid rgba(79, 141, 255, 0.82);
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
    font-family: "Google Sans", "Segoe UI Variable", "Segoe UI";
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
    border: 1px solid transparent;
}

QPushButton#NavButton:hover {
    background: rgba(255, 255, 255, 0.06);
}

QPushButton#NavButton:checked {
    background: rgba(79, 141, 255, 0.18);
    border: 1px solid rgba(79, 141, 255, 0.5);
}

QPushButton#NavButton[activeDownloads="true"] {
    background: transparent;
    border: 2px solid rgba(111, 167, 255, 0.78);
    color: #e6edf3;
}

QPushButton#NavButton[activeDownloads="true"]:hover {
    background: rgba(79, 141, 255, 0.10);
}

QPushButton#NavButton[pulse="true"] {
    background: rgba(79, 141, 255, 0.2);
    border: 1px solid rgba(111, 167, 255, 0.9);
}

QFrame#Card, QFrame#LibraryCard {
    background: rgba(36, 45, 60, 0.95);
    border: 1px solid rgba(230, 237, 243, 24);
    border-radius: 16px;
}

QFrame#OptionsCard {
    background: rgba(36, 45, 60, 0.95);
    border: 1px solid rgba(230, 237, 243, 24);
    border-radius: 16px;
}

QDialog, QMessageBox {
    background: #1f2633;
    color: #e6edf3;
}

QDialog QLabel, QMessageBox QLabel {
    color: #e6edf3;
}

QDialog QTextEdit, QMessageBox QTextEdit {
    background: #202939;
    color: #e6edf3;
    border: 1px solid rgba(230, 237, 243, 0.2);
    border-radius: 8px;
}

QDialogButtonBox QPushButton, QMessageBox QPushButton {
    background: rgba(25, 32, 45, 0.85);
    border: 1px solid rgba(230, 237, 243, 0.2);
    border-radius: 10px;
    padding: 6px 12px;
    color: #e6edf3;
}

QDialogButtonBox QPushButton:hover, QMessageBox QPushButton:hover {
    background: rgba(79, 141, 255, 0.18);
    border: 1px solid rgba(79, 141, 255, 0.55);
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
QLabel#LibraryTitle {
    font-weight: 600;
}

QLabel#InfoTitle {
    font-size: 14px;
    font-weight: 600;
}

QLabel#InfoSubtle {
    color: #b2becc;
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

QPushButton#PrimaryButton:disabled {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(79, 141, 255, 0.55), stop:1 rgba(42, 201, 194, 0.55));
    color: rgba(255, 255, 255, 0.75);
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

QPushButton#GhostButton:disabled {
    background: rgba(25, 32, 45, 0.65);
    border: 1px solid rgba(230, 237, 243, 0.2);
    color: rgba(230, 237, 243, 0.55);
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
    background: #1f2633;
    border: 1px solid rgba(230, 237, 243, 0.2);
    selection-background-color: rgba(79, 141, 255, 0.3);
    selection-color: #ffffff;
    color: #e6edf3;
}

QComboBox QAbstractItemView::item {
    background: transparent;
    color: #e6edf3;
}

QListView#ComboPopupView {
    background: #1f2633;
    border: 1px solid rgba(230, 237, 243, 0.2);
    color: #e6edf3;
    selection-background-color: rgba(79, 141, 255, 0.3);
    selection-color: #ffffff;
}

QListView#ComboPopupView::item {
    padding: 6px 10px;
}

QAbstractItemView, QAbstractItemView::item {
    background: #1f2633;
    color: #e6edf3;
    selection-background-color: rgba(79, 141, 255, 0.3);
    selection-color: #ffffff;
}

QProgressBar {
    background: rgba(34, 43, 58, 0.9);
    border: 1px solid rgba(230, 237, 243, 40);
    border-radius: 10px;
    text-align: center;
    height: 18px;
    padding: 2px;
    color: #e6edf3;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border-radius: 8px;
}

QProgressBar#FetchBar {
    background: rgba(79, 141, 255, 0.18);
    border: none;
    height: 4px;
    padding: 0px;
    border-radius: 2px;
}

QProgressBar#FetchBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border-radius: 2px;
}

QProgressBar#LibraryNavPulse {
    background: rgba(79, 141, 255, 0.2);
    border: none;
    border-radius: 2px;
    margin-left: 8px;
    margin-right: 8px;
}

QProgressBar#LibraryNavPulse::chunk {
    background: #70a7ff;
    border-radius: 2px;
}

QToolButton#ThumbButton {
    border: none;
    background: transparent;
    padding: 0px;
    margin: 0px;
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

QCheckBox#ThumbToggle {
    spacing: 8px;
    font-weight: 500;
    color: #d9e4ef;
}

QCheckBox#ThumbToggle::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid rgba(230, 237, 243, 0.48);
    background: rgba(34, 43, 58, 0.9);
}

QCheckBox#ThumbToggle::indicator:hover {
    border: 1px solid rgba(79, 141, 255, 0.82);
}

QCheckBox#ThumbToggle::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8dff, stop:1 #2ac9c2);
    border: 1px solid rgba(79, 141, 255, 0.84);
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
