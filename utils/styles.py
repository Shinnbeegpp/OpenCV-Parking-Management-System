# utils/styles.py
# Global stylesheet and color constants for ParkEase

COLORS = {
    'bg':        '#0F1117',
    'bg_card':   '#161B22',
    'bg_input':  '#1C2130',
    'bg_hover':  '#1E2537',
    'border':    '#2A3145',
    'primary':   '#3B82F6',
    'primary_h': '#2563EB',
    'success':   '#10B981',
    'warning':   '#F59E0B',
    'danger':    '#EF4444',
    'text':      '#F1F5F9',
    'text_muted':'#94A3B8',
    'text_dim':  '#64748B',
    'accent':    '#6366F1',
}

MAIN_STYLE = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
    font-size: 13px;
}}

QLabel {{
    color: {COLORS['text']};
    background: transparent;
}}

QPushButton {{
    background-color: {COLORS['primary']};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 9px 20px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
}}
QPushButton:hover {{
    background-color: {COLORS['primary_h']};
}}
QPushButton:pressed {{
    background-color: #1D4ED8;
}}
QPushButton:disabled {{
    background-color: {COLORS['border']};
    color: {COLORS['text_dim']};
}}

QTableWidget QPushButton {{
    min-height: 0px;
}}

QPushButton[btnStyle="secondary"] {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
}}
QPushButton[btnStyle="secondary"]:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['primary']};
}}

QPushButton[btnStyle="danger"] {{
    background-color: {COLORS['danger']};
}}
QPushButton[btnStyle="danger"]:hover {{
    background-color: #DC2626;
}}

QPushButton[btnStyle="success"] {{
    background-color: {COLORS['success']};
}}
QPushButton[btnStyle="success"]:hover {{
    background-color: #059669;
}}

QLineEdit, QComboBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    min-height: 36px;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {COLORS['primary']};
    outline: none;
}}
QLineEdit::placeholder {{
    color: {COLORS['text_dim']};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['primary']};
}}

QTableWidget {{
    background-color: {COLORS['bg_card']};
    alternate-background-color: {COLORS['bg']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    gridline-color: {COLORS['border']};
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {COLORS['border']};
}}
QTableWidget::item:selected {{
    background-color: {COLORS['primary']};
    color: white;
}}
QHeaderView::section {{
    background-color: {COLORS['bg']};
    color: {COLORS['text_muted']};
    font-size: 11px;
    font-weight: 600;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QScrollBar:vertical {{
    background: {COLORS['bg']};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    background-color: {COLORS['bg_card']};
    top: -1px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {COLORS['text_muted']};
    padding: 10px 20px;
    border: none;
    font-size: 13px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {COLORS['text']};
    border-bottom: 2px solid {COLORS['primary']};
}}
QTabBar::tab:hover {{
    color: {COLORS['text']};
}}

QGroupBox {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    margin-top: 16px;
    padding: 16px;
    font-size: 12px;
    font-weight: 600;
    color: {COLORS['text_muted']};
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    top: -8px;
}}

QSplitter::handle {{
    background-color: {COLORS['border']};
    width: 1px;
}}

QToolTip {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 4px 8px;
}}

QFrame[card="true"] {{
    background: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
}}

QFrame[card="inner"] {{
    background: {COLORS['bg_input']};
    border: 1px solid {COLORS['border']};
    border-radius: 7px;
}}

QPushButton[btnStyle="compact"] {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_muted']};
    border: 1px solid {COLORS['border']};
    border-radius: 7px;
    font-size: 12px;
    font-weight: 600;
    padding: 0 12px;
    min-height: 0px;
}}
QPushButton[btnStyle="compact"]:hover {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text']};
}}
"""

CARD_STYLE = f"""
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 16px;
"""

NAV_STYLE = f"""
    background-color: {COLORS['bg_card']};
    border-right: 1px solid {COLORS['border']};
"""

NAV_BTN_STYLE = f"""
QPushButton {{
    background-color: transparent;
    color: {COLORS['text_muted']};
    border: none;
    border-radius: 8px;
    padding: 12px 16px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
    min-width: 180px;
}}
QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text']};
}}
QPushButton[active="true"] {{
    background-color: {COLORS['primary']};
    color: white;
}}
"""
