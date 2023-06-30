# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Brush
                                 A QGIS plugin
 This plugin provides a tool for drawing polygons like with a brush in photoshop and GIMP
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-02-18
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Joseph Burkhart
        email                : josephburkhart.public@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# Import QGIS Qt libraries
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon, QColor, QPixmap, QCursor, QGuiApplication
from qgis.PyQt.QtWidgets import QAction

# Import necessary QGIS classes
from qgis.core import QgsFeature, QgsProject, QgsGeometry, QgsVectorLayer,\
    QgsRenderContext, QgsLayerTreeGroup, QgsWkbTypes, QgsMapLayer

# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the DockWidget
from .brush_dockwidget import BrushDockWidget
import os.path

# Import the brush tool code
from .brushtools import BrushTool

class Brush:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # Save reference to the QGIS status bar
        self.iface.statusBarIface()

        # Save additional references
        self.tool = None
        self.tool_name = None
        self.prev_tool = None

        self.layer_color = QColor(60, 151, 255, 127)

        self.sb = self.iface.statusBarIface()

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'Brush_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Draw by Brush')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'Brush')
        self.toolbar.setObjectName(u'Brush')

        self.pluginIsActive = False
        self.dockwidget = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('Brush', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        checkable=False,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        menu=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        action.setCheckable(checkable)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/brush/resources/paintbrush.png'
        self.brush_action = self.add_action(
            icon_path,
            text=self.tr(u'Brush Tool'),
            checkable=True,
            callback=self.activate_brush_tool,
            enabled_flag=False,
            parent=self.iface.mainWindow())

        # Get necessary info whenever active layer changes
        self.iface.currentLayerChanged.connect(self.configure_active_layer)

        # Only enable brush action if a Polygon or MultiPolygon Vector layer
        # is selected
        self.iface.currentLayerChanged.connect(self.enable_brush_action_check)
        
    def enable_brush_action_check(self):
        """Enable/Disable brush action as necessary when different types of
        layers are selected. Tool can only be activated when editing is on."""

        active_layer = self.iface.activeLayer()

        # No layer is selected
        if active_layer == None:
            self.disable_action(self.brush_action)

        # Polygon Layer is Selected
        if ((active_layer.type() == QgsMapLayer.VectorLayer) and
            (active_layer.geometryType() == QgsWkbTypes.PolygonGeometry) and
            active_layer.isEditable()):
                self.brush_action.setEnabled(True)
        
        # Non-polygon layer is selected
        else:
            self.disable_action(self.brush_action)
    
    def disable_action(self, action):
        """Procedure for disabling actions"""
        # Toggle off
        action.setChecked(False)  #uncheck

        # Disable the tool
        action.setEnabled(False)  #disable

        # Restore previous map tool (if any)
        # TODO: account for selected layer type
        if self.prev_tool != None:
            self.iface.mapCanvas().setMapTool(self.prev_tool)

    def configure_active_layer(self):
        """Reset the instance attributes and reconnect signals to slots as
        necessary. To be called whenever the active layer changes."""
        self.active_layer = self.iface.activeLayer()
        if ((self.active_layer != None) and
            (self.active_layer.type() == QgsMapLayer.VectorLayer)):
            self.active_layer.editingStarted.connect(self.enable_brush_action_check)
            self.active_layer.editingStopped.connect(self.enable_brush_action_check)

    #--------------------------------------------------------------------------
    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Draw by Brush'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------
    def activate_brush_tool(self):
        """Activate and run the brush tool"""
        # Load and start the plugin
        if not self.pluginIsActive:
            self.pluginIsActive = True

        # Save reference to current active map tool
        self.prev_tool = self.iface.mapCanvas().mapTool()

        # Reset the tool if another one is active -- TODO: this is not useful
        if self.tool:
            self.tool.reset()

        # Initialize and configure self.tool
        self.tool=BrushTool(self.iface)
        self.tool.setAction(self.actions[0])
        #self.tool.selectionDone.connect(self.draw)
        self.tool.rbFinished.connect(lambda g: self.draw(g))
        self.tool.move.connect(self.updateSB)
        
        # Select the tool in the current interface
        self.iface.mapCanvas().setMapTool(self.tool)
        
        # Set attributes that describe the drawing mode (will be used in
        # self.draw below)
        self.tool_name = 'draw_brush'

        # Save reference to active layer
        active_layer = self.iface.layerTreeView().currentLayer()

        # set name
        name = 'brush drawings'

        # Layer for brush drawing tool
        if self.tool_name == 'draw_brush':
            # If a polygon layer isn't selected
            if not active_layer or active_layer.geometryType() != QgsWkbTypes.PolygonGeometry:
                # Make a new layer
                layer_uri = (
                    f"Polygon?crs="
                    f"{self.iface.mapCanvas().mapSettings().destinationCrs().authid()}"
                    f"&field={self.tr('Drawings')}:string(255)"
                )
                active_layer = QgsVectorLayer(layer_uri, name, "memory")
            
                # Add new layer to map canvas
                project = QgsProject.instance() #TODO: make this an instance attribute so everything has access to it
                new_map_layer = project.addMapLayer(active_layer, False)

                # Add new layer to Drawings group (make group if it doesn't exist)
                if project.layerTreeRoot().findGroup(self.tr('Drawings')) is None:
                    project.layerTreeRoot().insertChildNode(
                        0, QgsLayerTreeGroup(self.tr('Drawings'))
                    )
                group = project.layerTreeRoot().findGroup(self.tr('Drawings'))
                group.insertLayer(0, active_layer)

                # Select the new layer so that it is active for the next drawing
                self.iface.setActiveLayer(new_map_layer)

                # Refresh the interface
                self.iface.layerTreeView().refreshLayerSymbology(active_layer.id())
                self.iface.mapCanvas().refresh()
            
            # Save reference as instance attribute, update the tool attribute as well
            self.active_layer = active_layer
            self.tool.active_layer = active_layer

        # Reset the status bar
        self.resetSB()

    def resetSB(self):
        """Reset the status bar"""
        message = {
            'draw_brush': 'Maintain the left click to draw with a brush.'
        }
        self.sb.showMessage(self.tr(message[self.tool_name]))

    def updateSB(self):
        """Update the status bar"""
        pass #TODO: placeholder

    def draw(self, g):
        """This is the actual drawing state"""
        # Get current active layer used in the drawing tool
        self.active_layer = self.tool.active_layer

        # Set flags
        drawing_mode = self.tool.mouse_state

        # Layer editing
        self.active_layer.startEditing()    #TODO: this causes error when a layer is selected, then the tool is activated, then the layer is deselected (active_layer becomes None, and None has no method start_editing)
        
        # Create new feature
        new_feature = QgsFeature()
        new_feature.setGeometry(g)
        
        # Find overlapping features
        overlapping_features = []
        for f in self.active_layer.getFeatures():
            if f.geometry().overlaps(new_feature.geometry()):        # if performance issues, use QgsGeometryEngine instead
                overlapping_features.append(f)

        # If drawing, merge new feature with any previous overlapping features
        # NOTE: MERGING REMOVES THE OVERLAPPING FEATURES! DO NOT USE THIS TOOL
        #       ON LAYERS WITH ATTRIBUTE DATA!
        # TODO: make this tool prompt the user on merging the attribute data
        if drawing_mode == 'drawing_with_brush':
            for f in overlapping_features:
                new_feature.setGeometry(new_feature.geometry().combine(f.geometry()))
                self.active_layer.deleteFeature(f.id())
            
            # Add new feature and commit changes
            self.active_layer.dataProvider().addFeatures([new_feature])
            self.active_layer.commitChanges()

        # If erasing, modify existing features
        if drawing_mode == 'erasing_with_brush':
            for f in overlapping_features:
                old_geom = f.geometry()
                new_geom = old_geom.difference(new_feature.geometry())
                f.setGeometry(new_geom)
                self.active_layer.updateFeature(f)

            self.active_layer.commitChanges()

        # Delete the instance of new_feature to free up memory
        del new_feature

        # Refresh the interface
        self.iface.layerTreeView().refreshLayerSymbology(self.active_layer.id())
        self.iface.mapCanvas().refresh()

        # Clean up at the end
        self.tool.reset()
        self.resetSB()