from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsWkbTypes
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'utilities', 'qpansopy_holding_dockwidget.ui'))


class QPANSOPYHoldingDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)

        # Setup layer selector
        self.routingLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        self._refresh_routing_layers_visible()
        self._prefill_routing_with_active_layer()
        try:
            QgsProject.instance().layerTreeRoot().visibilityChanged.connect(
                self._refresh_routing_layers_visible
            )
        except Exception:
            pass

        # Defaults
        self.altitudeUnitCombo.setCurrentText('ft')
        self.outputFolderLineEdit.setText(self._get_desktop())

        # Signals
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self._browse)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        # Refresh defaults and visibility-filtered list
        self._refresh_routing_layers_visible()
        self._prefill_routing_with_active_layer()

    def _get_desktop(self):
        if os.name == 'nt':
            return os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')
        return os.path.expanduser('~/Desktop')

    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select Output Folder', self.outputFolderLineEdit.text())
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def _prefill_routing_with_active_layer(self):
        """If active layer is a visible line, preselect it—only when current is missing."""
        try:
            current = self.routingLayerComboBox.currentLayer()
            if current and QgsProject.instance().mapLayer(current.id()):
                node = QgsProject.instance().layerTreeRoot().findLayer(current.id())
                if node and node.isVisible():
                    return  # keep user's current valid visible selection

            active = self.iface.activeLayer()
            if not active or not hasattr(active, "geometryType"):
                return
            if active.geometryType() != QgsWkbTypes.LineGeometry:
                return
            node = QgsProject.instance().layerTreeRoot().findLayer(active.id())
            if node and not node.isVisible():
                return
            self.routingLayerComboBox.setLayer(active)
        except Exception:
            pass

    def _refresh_routing_layers_visible(self):
        """Limit routing combo to visible line layers only."""
        try:
            project = QgsProject.instance()
            root = project.layerTreeRoot()
            if not root:
                return
            visible_lines = []
            for layer in project.mapLayers().values():
                try:
                    if not hasattr(layer, "geometryType"):
                        continue
                    if layer.geometryType() != QgsWkbTypes.LineGeometry:
                        continue
                    node = root.findLayer(layer.id())
                    if node and node.isVisible():
                        visible_lines.append(layer)
                except Exception:
                    continue
            excepted = [l for l in project.mapLayers().values() if l not in visible_lines]
            self.routingLayerComboBox.setExceptedLayerList(excepted)

            current = self.routingLayerComboBox.currentLayer()
            if current and current not in visible_lines:
                self._prefill_routing_with_active_layer()
        except Exception:
            pass

    def log(self, msg):
        if hasattr(self, 'logTextEdit') and self.logTextEdit:
            self.logTextEdit.append(msg)
            self.logTextEdit.ensureCursorVisible()

    def calculate(self):
        lyr = self.routingLayerComboBox.currentLayer()
        if not lyr:
            self.log('Error: Please select a routing layer')
            return

        if lyr.selectedFeatureCount() == 0:
            self.log('Error: Please select one segment before calculation')
            return

        try:
            params = {
                'IAS': float(self.iasLineEdit.text()),
                'altitude': float(self.altitudeLineEdit.text()),
                'altitude_unit': self.altitudeUnitCombo.currentText(),
                'isa_var': float(self.isaVarLineEdit.text()),
                'bank_angle': float(self.bankAngleLineEdit.text()),
                'leg_time_min': float(self.legTimeLineEdit.text()),
                'turn': 'L' if self.leftTurnRadio.isChecked() else 'R',
                'output_dir': self.outputFolderLineEdit.text(),
            }

            from ...modules.utilities.holding import run_holding_pattern
            res = run_holding_pattern(self.iface, lyr, params)
            if res:
                self.log('Holding pattern created successfully')
        except Exception as e:
            import traceback
            self.log(f"Error during calculation: {e}")
            self.log(traceback.format_exc())
