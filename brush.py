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
    QgsRenderContext, QgsLayerTreeGroup

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

        self.bGeom = None

        self.color = QColor(60, 151, 255, 255)

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

        #print "** INITIALIZING Brush"

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
        self.add_action(
            icon_path,
            text=self.tr(u'Brush Tool'),
            checkable=True,
            callback=self.draw_brush,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------
    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING Brush"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD Brush"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Draw by Brush'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------
    def draw_brush(self):
        """Activate and run the brush tool"""
        # Load and start the plugin
        if not self.pluginIsActive:
            self.pluginIsActive = True

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = BrushDockWidget()

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # show the dockwidget
            self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

        # Reset the tool if another one is active
        if self.tool:
            self.tool.reset()

        # Initialize and configure self.tool
        self.tool=BrushTool(self.iface, self.color)
        self.tool.setAction(self.actions[0])
        #self.tool.selectionDone.connect(self.draw)
        self.tool.rbFinished.connect(self.draw)
        self.tool.move.connect(self.updateSB)
        
        # Select the tool in the current interface
        self.iface.mapCanvas().setMapTool(self.tool)
        
        # Set attributes that describe the drawing mode (will be used in
        # self.draw below)
        self.draw_shape = 'brush_stroke'
        self.tool_name = 'draw_brush'
        
        # Reset the status bar
        self.resetSB()

        # Set cursor shape and size
        mycursorpixmap=QPixmap(':/plugins/brush/resources/redcircle_500x500.png')
        newpm = mycursorpixmap.scaled(20,20)
        mymousecursor=QCursor(newpm)
        QGuiApplication.instance().setOverrideCursor(mymousecursor)

    def resetSB(self):
        """Reset the status bar"""
        message = {
            'draw_brush': 'Maintain the left click to draw with a brush.'
        }
        self.sb.showMessage(self.tr(message[self.tool_name]))

    def updateSB(self):
        """Update the status bar"""
        pass #TODO: placeholder

    def draw(self):
        """This is the actual drawing state"""
        # Initialize rubber band and geometry (this is probably not necessary)
        rb = self.tool.rb
        g = rb.asGeometry()
        #print('added line of length '+str(len(g.asPolyline())))
        # Set flags
        ok = True
        warning = False
        errBuffer_noAtt = False
        errBuffer_Vertices = False
        add_to_existing_layer = False

        # Save reference to active layer
        layer = self.iface.layerTreeView().currentLayer()

        # set name
        name = 'brush drawings'

        # Create layer for brush drawing tool
        if self.tool_name == 'draw_brush':
            layer_uri = (
                f"Polygon?crs="
                f"{self.iface.mapCanvas().mapSettings().destinationCrs().authid()}"
                f"&field={self.tr('Drawings')}:string(255)"
            )
            layer = QgsVectorLayer(layer_uri, name, "memory")

        # Layer editing
        layer.startEditing()
        symbols = layer.renderer().symbols(QgsRenderContext()) #original note: which context?
        symbols[0].setColor(self.color)
        feature = QgsFeature()
        feature.setGeometry(g)
        # feature.setAttribute([name])
        layer.dataProvider().addFeatures([feature])
        #print('added line of length '+str(len(g.asPolyline())))
        layer.commitChanges()

        # Add new layer if necessary 
        if not add_to_existing_layer:
            project = QgsProject.instance()
            project.addMapLayer(layer, False)

            # Add new layer to Drawings group (make group if it doesn't exist)
            if project.layerTreeRoot().findGroup(self.tr('Drawings')) is None:
                project.layerTreeRoot().insertChildNode(
                    0, QgsLayerTreeGroup(self.tr('Drawings'))
                )
            group = project.layerTreeRoot().findGroup(self.tr('Drawings'))
            group.insertLayer(0, layer)
        
        # Refresh the interface
        self.iface.layerTreeView().refreshLayerSymbology(layer.id())
        self.iface.mapCanvas().refresh()

        # Clean up at the end
        self.tool.reset()
        self.resetSB()
        self.bGeom = None