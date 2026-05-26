import sys
from PyQt6.QtWidgets import QApplication
from biopro.core.state import ApplicationState
# this script would try to trigger the background worker, but it's too complex to mock FlowState easily.
