# utils/qt_imports.py

import sys

try:
    from PyQt6.QtWidgets import *
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
    QT_VERSION = 6
except ImportError:
    try:
        from PyQt5.QtWidgets import *
        from PyQt5.QtCore import *
        from PyQt5.QtGui import *
        QT_VERSION = 5
    except ImportError:
        print("Error: PyQt5 or PyQt6 must be installed!")
        print("Installation: pip install PyQt6 pillow")
        sys.exit(1)
