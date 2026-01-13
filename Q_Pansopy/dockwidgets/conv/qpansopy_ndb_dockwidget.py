from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, Qt
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsWkbTypes
import os
import datetime

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'conv', 'qpansopy_ndb_dockwidget.ui'))

class QPANSOPYNDBDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super(QPANSOPYNDBDockWidget, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface

        # Setup layer combobox
        self.routingLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        self._refresh_routing_layers_visible()
        self._prefill_routing_with_active_layer()
        try:
            QgsProject.instance().layerTreeRoot().visibilityChanged.connect(
                self._refresh_routing_layers_visible
            )
        except Exception:
            pass
        
        # Set default output folder
        self.outputFolderLineEdit.setText(self.get_desktop_path())
        
        # Connect signals
        self.calculateButton.clicked.connect(self.calculate)
        self.browseButton.clicked.connect(self.browse_output_folder)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        # Refresh defaults and visibility-filtered list
        self._refresh_routing_layers_visible()
        self._prefill_routing_with_active_layer()

    def get_desktop_path(self):
        if os.name == 'nt':
            return os.path.join(os.environ['USERPROFILE'], 'Desktop')
        return os.path.expanduser('~/Desktop')

    def browse_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.outputFolderLineEdit.text()
        )
        if folder:
            self.outputFolderLineEdit.setText(folder)

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

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

    def calculate(self):
        """Run the NDB approach areas calculation"""
        routing_layer = self.routingLayerComboBox.currentLayer()
        if not routing_layer:
            self.log("Error: Please select a routing layer")
            return
            
        # Verify that the user has at least one element selected
        if routing_layer.selectedFeatureCount() == 0:
            self.log("Error: Please select at least one segment in the map before calculation")
            return
        
        # Get export options
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()

        try:
            self.log("Calculating NDB Approach Areas...")
            from ...modules.conv.ndb_approach import run_ndb_approach
            result = run_ndb_approach(self.iface, routing_layer)

            # Log results
            if result:
                self.log("NDB Approach Areas calculation completed successfully")
                if export_kml:
                    # Add KML export code here if available
                    self.log(f"KML export would go to: {output_dir}")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
