from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, Qt
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsWkbTypes
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', '..', 'ui', 'pbn', 'qpansopy_gnss_waypoint_dockwidget.ui'))


class QPANSOPYGNSSWaypointDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface):
        super(QPANSOPYGNSSWaypointDockWidget, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface

        # Setup layer comboboxes
        self.waypointLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
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
        self.xttSpinBox.valueChanged.connect(self.update_att)
        
        # Initial ATT update
        self.update_att(self.xttSpinBox.value())

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        # Refresh defaults and visibility-filtered list
        self._refresh_routing_layers_visible()
        self._prefill_routing_with_active_layer()

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
            # Exclude all non-visible layers from the combo
            excepted = [l for l in project.mapLayers().values() if l not in visible_lines]
            self.routingLayerComboBox.setExceptedLayerList(excepted)

            # If current selection became invisible, try to refill
            current = self.routingLayerComboBox.currentLayer()
            if current and current not in visible_lines:
                self._prefill_routing_with_active_layer()
        except Exception:
            pass

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

    def update_att(self, xtt_value):
        """Update ATT value (0.8 * XTT)"""
        att = xtt_value * 0.8
        self.attLineEdit.setText(f"{att:.2f}")

    def log(self, message):
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()

    def calculate(self):
        """Run the GNSS waypoint tolerance calculation"""
        waypoint_layer = self.waypointLayerComboBox.currentLayer()
        routing_layer = self.routingLayerComboBox.currentLayer()
        
        if not waypoint_layer:
            self.log("Error: Please select a waypoint (point) layer")
            return
            
        if not routing_layer:
            self.log("Error: Please select a routing (line) layer")
            return
            
        # Check for selection
        if waypoint_layer.selectedFeatureCount() == 0:
            self.log("Error: Please select at least one waypoint in the map")
            self.log("Tip: Use the selection tool to select the waypoint(s)")
            return
            
        if routing_layer.selectedFeatureCount() == 0:
            self.log("Error: Please select the routing segment for azimuth calculation")
            return
        
        # Get parameters
        xtt = self.xttSpinBox.value()
        export_kml = self.exportKmlCheckBox.isChecked()
        output_dir = self.outputFolderLineEdit.text()

        try:
            self.log(f"Creating GNSS Waypoint tolerance with XTT={xtt} NM...")
            
            from ...modules.pbn.gnss_waypoint import run_gnss_waypoint
            
            params = {
                'xtt': xtt,
                'export_kml': export_kml,
                'output_dir': output_dir
            }
            
            result = run_gnss_waypoint(self.iface, waypoint_layer, routing_layer, params)
            
            if result:
                self.log("GNSS Waypoint tolerance calculation completed successfully")
                if export_kml and 'kml_path' in result:
                    self.log(f"KML exported to: {result['kml_path']}")
            else:
                self.log("Calculation completed with no result returned")
                
        except Exception as e:
            self.log(f"Error during calculation: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
