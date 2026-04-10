"""
evaluate_gui.py  —  TB_CPA_Evaluate
=====================================
Launch the evaluation pipeline GUI.

Run with:
    python TB_CPA_Evaluate/evaluate_gui.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui import main

if __name__ == "__main__":
    main()
