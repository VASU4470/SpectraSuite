import sys
import os
import subprocess
import ctypes
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                               QGridLayout, QPushButton, QLabel, QMessageBox)
from PySide6.QtCore import Qt, QTimer

class WelcomeDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analytical Spectroscopy Suite")
        self.resize(700, 500)
        self.resize(700, 500)
        self.running_apps = {}
        
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e2e; /* Deep dark blue/grey background */
                color: #cdd6f4;            /* Off-white text */
            }
            QLabel#Title {
                font-size: 26px;
                font-weight: bold;
                color: #89b4fa;            /* Soft blue accent for title */
            }
            QLabel#Subtitle {
                font-size: 14px;
                color: #a6adc8;            /* Muted text for subtitles */
            }
            QPushButton {
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 15px;       /* Smooth rounded corners */
                font-size: 16px;
                font-weight: bold;
                padding: 15px;
            }
            QPushButton:hover {
                background-color: #45475a;
                border: 2px solid #89b4fa; /* Blue glow border on hover */
            }
            QPushButton:pressed {
                background-color: #585b70; /* Lighter color when clicked */
            }
        """)
        
        self.setup_ui()

    def setup_ui(self):
        # Main vertical layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Headers
        title = QLabel("Analytical Spectroscopy Suite")
        title.setObjectName("Title") # Links to the QSS #Title style above
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Select a workspace to begin")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # Grid layout for buttons
        grid = QGridLayout()
        grid.setSpacing(20)

        self.modules = [
            ("FT-IR\nSpectroscopy", "ir.py", "📈"),
            #("Raman\nSpectroscopy", None, "🔬"),
            #("UV-Vis\nSpectroscopy", None, "🌈"),
            ("XRD\nAnalysis", "xrd.py", "📊"),
            #("XPS\nAnalysis", None, "⚡"),
            #("General\nPlotter", "plotter.py", "✏️")
        ]

        # Build the buttons
        for i, (name, target, icon) in enumerate(self.modules):
            btn = QPushButton(f"{icon}\n\n{name}")
            btn.setMinimumHeight(120)
            btn.setCursor(Qt.PointingHandCursor) # Changes mouse to a hand
            
            if target in ["ir.py", "xrd.py"]:
                # Connect the button click to our launch function
                btn.clicked.connect(lambda checked=False, b=btn, t=target, n=name, ic=icon: self.launch_app(b, t, n, ic))
            else:
                btn.clicked.connect(self.coming_soon)
                
            grid.addWidget(btn, i // 3, i % 3)

        layout.addLayout(grid)

        # Footer
        footer = QLabel("Version 1.0")
        footer.setObjectName("Subtitle")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

    def launch_app(self, btn, target_script, original_name, icon):
        # 1. Check if the app is already running!
        if target_script in self.running_apps:
            process = self.running_apps[target_script]
            if process.poll() is None: # None means it is still actively running
                QMessageBox.warning(self, "Already Running", f"{original_name} is already open or loading.\nPlease wait a moment or check your taskbar.")
                return # Stop right here, do not launch a duplicate!

        # 2. If it's not running, proceed with launching
        btn.setText("⏳\n\nStarting...")
        btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            # 1. Get the absolute path to the script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            target_path = os.path.join(script_dir, target_script)
            
            # 2. Tell the process to run INSIDE that folder (cwd)
            process = subprocess.Popen(
                [sys.executable, target_path], 
                cwd=script_dir
            )
            self.running_apps[target_script] = process
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Could not start {target_script}.\nError: {e}")
            
        # 3. Reset the button visuals after 3 seconds
        QTimer.singleShot(3000, lambda: self.reset_button(btn, original_name, icon))

    def reset_button(self, btn, original_name, icon):
        btn.setText(f"{icon}\n\n{original_name}")
        btn.setEnabled(True)
        QApplication.restoreOverrideCursor() # Back to normal mouse

    def coming_soon(self):
        QMessageBox.information(self, "Module In Development", "This workspace is currently being built. Please check back in the next version!")

if __name__ == "__main__":
    # 1. Tell Windows this is a unique app to fix the taskbar icon grouping
    try:
        myappid = 'analytical.spectroscopy.suite.1.0' # A unique ID for your app
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass # If the user is on a Mac or Linux, this safely does nothing

    app = QApplication(sys.argv)
    
    # 2. Set the global icon for the application (Window and Taskbar)
    # Make sure you have a file named 'icon.png' or 'icon.ico' in your folder!
    app.setWindowIcon(QIcon("icon.png")) 
    
    window = WelcomeDashboard()
    window.show()
    sys.exit(app.exec())