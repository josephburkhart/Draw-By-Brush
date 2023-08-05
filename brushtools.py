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
from __future__ import print_function
from builtins import str
from builtins import range

from qgis.gui import QgsMapTool, QgsRubberBand, QgsMapToolEmitPoint, \
    QgsProjectionSelectionDialog
from qgis.core import QgsWkbTypes, QgsPointXY, QgsPoint, QgsGeometry, \
    QgsRenderContext, QgsLineString, QgsCoordinateTransform, QgsProject

from qgis.PyQt.QtCore import Qt, QCoreApplication, pyqtSignal, QPoint
from qgis.PyQt.QtWidgets import QDialog, QLineEdit, QDialogButtonBox, \
    QGridLayout, QLabel, QGroupBox, QVBoxLayout, QComboBox, QPushButton, \
    QInputDialog, QApplication, QShortcut
from qgis.PyQt.QtGui import QDoubleValidator, QIntValidator, QKeySequence, \
    QPixmap, QCursor, QPainter, QColor, QTransform

from math import sqrt, pi, cos, sin

from PyQt5.QtGui import QGuiApplication

# Initialize Qt resources from file resources.py
from .resources import *

class BrushTool(QgsMapTool):
    """
    Brush drawing tool.
    Patterned off of `drawtools.py` from the qdraw plugin.
    """
    # Make signals for movement and end of selection and end of drawing
    selectionDone = pyqtSignal()
    move = pyqtSignal()
    rbFinished = pyqtSignal(QgsGeometry)    # from BeePen

    def __init__(self, iface):
        QgsMapTool.__init__(self, iface.mapCanvas())

        # Save references to QGIS interface and current active layer
        self.canvas = iface.mapCanvas()
        self.iface = iface
        self.active_layer = iface.activeLayer()
        
        # Set reprojection flag if active_layer has different crs from map canvas
        self.reproject_necessary = False
        if self.active_layer != None:
            if self.canvas.project().crs().authid() != self.active_layer.sourceCrs().authid():
                self.reproject_necessary = True
                self.t = QgsCoordinateTransform(
                    self.canvas.project().crs(),
                    self.active_layer.sourceCrs(),
                    QgsProject.instance()
                )
        
        # Configure Rubber Band for Drawing
        self.rb = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rb.setWidth(1)

        # Set default brush parameters
        self.brush_radius = 120 #originally 40
        self.brush_points = 64
        self.brush_angle = 0
        self.brush_shapes = ['circle', 'wedge']
        self.brush_shape = self.brush_shapes[0]

        self.drawing_mode = 'free'

        self.merging = False

        # Shortcut
        self.tab_shortcut = QShortcut(QKeySequence(Qt.Key_Tab), self.iface.mainWindow())
        self.tab_shortcut.activated.connect(self.switch_brush_shape)

        # Set default tool colors
        self.draw_color = QColor(0,0,255,127)    # transparent blue
        self.erase_color = QColor(255,0,0,127)   # transparent red

        # Reset the rubberband
        self.reset()

    def activate(self):
        """Run when tool is activated"""        #TODO: wrap this into __init__?
        self.make_cursor(self.brush_shape, self.brush_radius, self.brush_angle)

    def make_cursor(self, shape, radius, angle):
        """Sets the cursor to be a red circle scaled to a radius in px and
        rotated by an angle in degrees."""
        # Set cursor shape and size
        if shape == 'circle':
            brush_pixmap = QPixmap(':/plugins/brush/resources/redcircle_500x500.png')
        elif shape == 'wedge':
            brush_pixmap = QPixmap(':/plugins/brush/resources/redwedge_500x500.png')
        scaled_pixmap = brush_pixmap.scaled(radius*2,radius*2)
        xform = QTransform().rotate(angle)
        xformed_pixmap = scaled_pixmap.transformed(xform)
        brush_cursor=QCursor(xformed_pixmap)
        self.canvas.setCursor(brush_cursor)

    def wheelEvent(self, event):
        """If shift is pressed, rescale brush radius and redraw the cursor.
        If ctrl+shift is pressed, rotate and redraw the cursor."""
        if event.modifiers() == Qt.ShiftModifier:
            event.accept()
            d = event.angleDelta().y()
            self.brush_radius *= 1 + d/1000  #TODO: account for high-dpi mice
            self.make_cursor(self.brush_shape, int(self.brush_radius), int(self.brush_angle))
        
        elif event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            event.accept()
            d = event.angleDelta().y()
            self.brush_angle += d/50
            self.make_cursor(self.brush_shape, int(self.brush_radius), int(self.brush_angle))

    def switch_brush_shape(self):
        """Switch between the different brush shapes."""
        new_brush_index = self.brush_shapes.index(self.brush_shape) + 1
        if new_brush_index > len(self.brush_shapes) - 1:
            new_brush_index = 0
        self.brush_shape = self.brush_shapes[new_brush_index]
        self.make_cursor(self.brush_shape, int(self.brush_radius), int(self.brush_angle))

    def reset(self):
        self.prev_point = None
        self.rb.reset(QgsWkbTypes.PolygonGeometry)

    def circle_around_point(self, center, radius=0, num_points=0, map_units=False):
        """
        Creates a circular QgsGeometry centered on a point with the given 
        radius and num_points

        :type center: qgis.core.QgsPoint
        :param center: canvas point, in layer crs
        :type radius: float
        :param radius: cicle radius, considered to be in layer units
        :type num_points: int
        :param num_points: number of vertices
        :type map_units: bool
        :param map_units: whether the radius should be considered in map units
        :return: QgsGeometry of type QGis.Polygon

        Adapted from https://gis.stackexchange.com/a/69792
        """
        if not radius:
            radius = self.brush_radius #default brush radius
        
        if not map_units:
            context = QgsRenderContext().fromMapSettings(self.canvas.mapSettings())
            # scale factor is px / mm; as mm (converted to map pixels, then to map units)
            radius *= context.mapToPixel().mapUnitsPerPixel()
        if not num_points:
            num_points = self.brush_points

        points = []

        for i in range(num_points-1):
            theta = i * (2.0 * pi / (num_points-1))
            p = QgsPointXY(center.x() + radius * cos(theta),
                         center.y() + radius * sin(theta))
            points.append(p)
        
        return QgsGeometry.fromPolygonXY([points])

    def wedge_around_point(self, center, radius=0, theta=0, map_units=False):
        """Creates wedge shape around a central point with a given radius,
        rotates by an angle.
        
        Geometry matches :/plugins/brush/resources/redwedge_500x500.png."""
        if not radius:
            radius = self.brush_radius #default brush radius
        
        if not theta:  #TODO: remove checks like this (maybe remove to general module)
            theta = self.brush_angle

        if not map_units:
            context = QgsRenderContext().fromMapSettings(self.canvas.mapSettings())
            # scale factor is px / mm; as mm (converted to map pixels, then to map units)
            radius *= context.mapToPixel().mapUnitsPerPixel()

        # Convert theta to radians
        theta = theta*(pi/180)

        # Unrotated Points
        p1_x = center.x()
        p1_y = center.y() + radius
        
        p2_x = center.x() + (radius/2)
        p2_y = center.y() - (radius/2)

        p3_x = center.x() - (radius/2)
        p3_y = center.y() - (radius/2)

        # Rotated Points
        # TODO: maybe make the geometry with the above points and then rotate using
        #       QgsGeometry method. This would be easier to read for collaborators
        p1_x_r =    (p1_x - center.x())*cos(theta) + (p1_y - center.y())*sin(theta) + center.x()
        p1_y_r = -1*(p1_x - center.x())*sin(theta) + (p1_y - center.y())*cos(theta) + center.y()

        p2_x_r =    (p2_x - center.x())*cos(theta) + (p2_y - center.y())*sin(theta) + center.x()
        p2_y_r = -1*(p2_x - center.x())*sin(theta) + (p2_y - center.y())*cos(theta) + center.y()

        p3_x_r =    (p3_x - center.x())*cos(theta) + (p3_y - center.y())*sin(theta) + center.x()
        p3_y_r = -1*(p3_x - center.x())*sin(theta) + (p3_y - center.y())*cos(theta) + center.y()

        points = [
            QgsPointXY(p1_x_r, p1_y_r),
            QgsPointXY(p2_x_r, p2_y_r),
            QgsPointXY(p3_x_r, p3_y_r)
        ]

        return QgsGeometry.fromPolygonXY([points])


    def canvasPressEvent(self, event):
        """
        The following needs to happen:
          - apply the current brush to the rubber band
          - start tracking mouse movement

        """

        # Update reference to active layer
        self.active_layer = self.iface.activeLayer()
        if self.active_layer != None: 
            if self.canvas.project().crs().authid() != self.active_layer.sourceCrs().authid():
                self.reproject_necessary = True
                self.t = QgsCoordinateTransform(
                    self.canvas.project().crs(),
                    self.active_layer.sourceCrs(),
                    QgsProject.instance()
                )

        # Set status and color
        if event.button() == Qt.LeftButton:
            self.drawing_mode = 'drawing_with_brush'
            self.rb.setColor(self.draw_color)

            # If user pressed Ctrl, toggle the merging flag
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ControlModifier:
                self.merging = True
        
        elif event.button() == Qt.RightButton:
            self.drawing_mode = 'erasing_with_brush'
            self.rb.setColor(self.erase_color)
        
        # Create initial geometry
        point = self.toMapCoordinates(event.pos())
        if self.brush_shape == 'circle':
            self.rb.setToGeometry(self.circle_around_point(point), None) #changed
        elif self.brush_shape == 'wedge':
            self.rb.setToGeometry(self.wedge_around_point(point), None)
        
        # Create previous point and geometry tracker (used in canvasMoveEvent below)
        self.prev_point = point
        self.prev_geometry = self.rb.asGeometry()

    def canvasMoveEvent(self, event):
        """

        - prev_geometry: previous wedge or circle
        - current_geometry: current wedge or circle
        - new_geometry: what will be added to the rubberband
        """
        layer = self.active_layer

        if self.drawing_mode in ('drawing_with_brush','erasing_with_brush'):
            # Get current mouse location
            point = self.toMapCoordinates(event.pos())
            
            # Handle drawing with circular brush
            if self.brush_shape == 'circle':
                # Calculate line from previous mouse location
                mouse_move_line = QgsLineString([self.prev_point, point])

                # Calculate buffer distance (could be moved to canvasPressEvent)
                # scale factor is px / mm; as mm (converted to map pixels, then to map units)
                context = QgsRenderContext().fromMapSettings(self.canvas.mapSettings())
                radius = self.brush_radius
                radius *= context.mapToPixel().mapUnitsPerPixel()

                # Calculate new geometry
                new_geometry = QgsGeometry(mouse_move_line).buffer(radius, self.brush_points)

                # Set point tracker to current point
                self.prev_point = point

            # Handle drawing with wedge brush
            elif self.brush_shape == 'wedge':
                # Calculate new geometry
                current_geometry = self.wedge_around_point(point)
                new_geometry = current_geometry.combine(self.prev_geometry).convexHull()

                # Set geometry tracker to current geometry
                self.prev_geometry = current_geometry

            # Set new rubberband geometry
            self.rb.setToGeometry(self.rb.asGeometry().combine(new_geometry))

    def canvasReleaseEvent(self, event):
        """
        The following needs to happen:
          - check to see if rubber band intersects with any of the active feature
          - if so, add...
        """
        layer = self.active_layer
        geom = self.rb.asGeometry()
        # Reproject the rubberband geometry if necessary
        if self.reproject_necessary == True:
            new_geom = QgsGeometry(geom) #have to clone before transforming
            new_geom.transform(self.t)
        else:
            new_geom = geom

        # Simplify the rubberband geometry
        # tolerance value is calculated based on brush_radius and brush_points
        # scale factor is px / mm; as mm (converted to map pixels, then to map units)
        # TODO: move this calculation to __init__ above (but have to account
        #       for selecting a new layer with a different CRS)
        context = QgsRenderContext().fromMapSettings(self.canvas.mapSettings())
        radius = self.brush_radius
        radius *= context.mapToPixel().mapUnitsPerPixel()

        tolerance = (2*pi*radius)/(24*self.brush_points)

        new_geom = new_geom.simplify(tolerance)
        
        # Emit final geometry
        self.rbFinished.emit(new_geom)

        # refresh the canvas and reset the rubberband and flags
        self.reset()
        self.canvas.refresh()

        self.drawing_mode = 'free'

        self.merging = False

    def deactivate(self):
        self.rb.reset(True)
        self.tab_shortcut.setEnabled(False)
        QgsMapTool.deactivate(self)