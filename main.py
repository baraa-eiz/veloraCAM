import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import VeloraCNCMainWindow

def main():
    """
    Main bootstrap entry point for Velora CNC Modular CAM Suite.
    Initializes QApp loop and launches main interface window.
    """
    app = QApplication(sys.argv)
    
    # Establish high DPI scaling support
    app.setAttribute(Qt.AA_EnableHighDpiScaling if hasattr(Qt, 'AA_EnableHighDpiScaling') else None)
    
    window = VeloraCNCMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    from PySide6.QtCore import Qt
    main()
