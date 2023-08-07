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
    """Custom QgsMapTool to simulate drawing with a brush.
    
    Attributes:
        iface: The QgsInterface of the current project instance.
        canvas: The QgsMapCanvas of the current project instance.
        active_layer: The currently active map layer (can be any subclass of
            QgsMapLayer).
        brush_radius: An integer number representing the radius of the brush 
            in pixels.
        brush_points: An integer number of points to use when approximating a
            circle.
        brush_angle: A float representing the angle of the brush.
        brush_shapes: A list of strings indicating the names of the shapes the
            brush can take.
        brush_shape: A string of the name of the current shape of the brush.
        draw_color: The QColor to use for rendering the QgsRubberBand when in
            drawing mode.
        erase_color: The QColor to use for rendering the QgsRubberBand when in
            erasing mode.
        t: The QgsCoordinateTransform to be used in reprojecting the geometry
            from QgsRubberBand to the CRS of self.active_layer.
        drawing_mode: A string indicating the current mode of the Brush Tool.
        merging: A boolean indicating whether the geometry currently being
            drawn must be merged with other features in the active layer.
        reprojecting: A boolean indicating whether the geometry currently being
            drawn must be reprojected out of the project CRS to match the CRS
            of the active layer.
        tab_shortcut: A QShortcut that binds the tab key to the method that
            changes the brush shape.
        rb: The QgsRubberBand containing the geometry currently being drawn.
        previous_point: A QgsPointXY indicating the last recorded position of
            the mouse pointer.
        previous_geometry: A QgsGeometry containing the last recorded brush
            shape, to be used only with non-circle brushes.

    Methods:
        activate: Make the brush tool cursor whenever tool is activated.
        deactivate: Reset the rubber band and disable the tab shortcut whenever
            the tool is deactivated.
        make_cursor: Render the cursor using brush shape and size attributes.
        switch_brush_shape: Switch the brush to the next possible shape.
        check_coordinate_systems: Check that the active layer is in the same
            CRS as the project instance, and if not, modify the relevant
            attributes to prepare for reprojection.
        reset: Erase data in geometric attributes when the tool is reset.
        wheelEvent: When the user scrolls their mouse wheel, check for Shift 
            and Ctrl modifiers and update the cursor accordingly.
        canvasPressEvent: Create initial rubber band geometry based on current
            mouse position.
        canvasMoveEvent: Update rubber band geometry based on mouse movement.
        canvasReleaseEvent: Process rubber band geometry (simplify, reproject 
            if necessary) and then emit it for drawing into the active layer.
        circle_around_point: Calculate a circle geometry around a given point.
        wedge_around_point: Calculate a wedge geometry around a given point.

    """
    # Make signals for movement and end of selection and end of drawing
    rbFinished = pyqtSignal(QgsGeometry)    # from BeePen

    #------------------------------ INITIALIZATION ----------------------------
    def __init__(self, iface):
        """Constructor for the Brush Tool.

        Args:
            iface: A QgsInterface instance which provides the hook by which the
                class can manipulate the QGIS application at run time.
        """
        # Initialize the parent class
        QgsMapTool.__init__(self, iface.mapCanvas())

        # Save references to QGIS interface and current active layer
        self.canvas = iface.mapCanvas()
        self.iface = iface
        self.active_layer = iface.activeLayer()

        # Set other instance attributes
        self.brush_radius = 120                 # default brush parameters
        self.brush_points = 24
        self.brush_angle = 0
        self.brush_shapes = ['circle', 'wedge']
        self.brush_shape = self.brush_shapes[0]

        self.draw_color = QColor(0,0,255,127)    # default tool colors
        self.erase_color = QColor(255,0,0,127)

        self.t = None                            # coordinate transform

        # Set flags
        self.drawing_mode = 'inactive'
        self.merging = False
        self.reprojecting = False

        # Set shortcuts
        self.tab_shortcut = QShortcut(QKeySequence(Qt.Key_Tab), self.iface.mainWindow())
        self.tab_shortcut.activated.connect(self.switch_brush_shape)
        
        # Check if reprojection is necessary and if so update flags and attributes
        self.check_coordinate_systems()
        
        # Configure rubberband for drawing
        self.rb = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rb.setWidth(1)

        # Reset the rubberband
        self.reset()

    #------------------------------- ACTIVATION -------------------------------
    def activate(self):
        """Make the brush tool cursor whenever tool is activated."""        #TODO: wrap this into __init__?
        self.make_cursor(self.brush_shape, self.brush_radius, self.brush_angle)

    def deactivate(self):
        """Reset the rubber band and disable the tab shortcut whenever the tool
        is deactivated."""
        self.rb.reset(True)
        self.tab_shortcut.setEnabled(False)
        QgsMapTool.deactivate(self)

    #------------------------------ UPPDATE STATE -----------------------------
    def make_cursor(self, shape, radius, angle):
        """Render the cursor based on brush shape and size attributes."""
        # Set cursor shape and size
        if shape == 'circle':
            brush_pixmap = QPixmap(':/plugins/brush/resources/redcircle_500x500.png')
        elif shape == 'wedge':
            brush_pixmap = QPixmap(':/plugins/brush/resources/redwedge_500x500.png')
        scaled_pixmap = brush_pixmap.scaled(radius*2,radius*2)
        transformation = QTransform().rotate(angle)
        transformed_pixmap = scaled_pixmap.transformed(transformation)
        brush_cursor=QCursor(transformed_pixmap)
        self.canvas.setCursor(brush_cursor)

    def switch_brush_shape(self):
        """Switch the brush to the next possible shape."""
        new_brush_index = self.brush_shapes.index(self.brush_shape) + 1
        if new_brush_index > len(self.brush_shapes) - 1:
            new_brush_index = 0
        self.brush_shape = self.brush_shapes[new_brush_index]
        self.make_cursor(self.brush_shape, int(self.brush_radius), int(self.brush_angle))

    def check_coordinate_systems(self):
        """Check that the active layer is in the same CRS as the project 
        instance, and if not, update the reprojection flag and prepare the 
        necessary transformation."""
        self.active_layer = self.iface.activeLayer()
        if self.active_layer != None: 
            if self.canvas.project().crs().authid() != self.active_layer.sourceCrs().authid():
                self.reprojecting = True
                self.t = QgsCoordinateTransform(
                    self.canvas.project().crs(),
                    self.active_layer.sourceCrs(),
                    QgsProject.instance()
                )

    def reset(self):
        """Erase data in geometric attributes when the tool is reset."""
        self.previous_point = None
        self.previous_geometry = None
        self.rb.reset(QgsWkbTypes.PolygonGeometry)

    #------------------------------- INTERACTION ------------------------------
    def wheelEvent(self, event):
        """When the user scrolls their mouse wheel, check for Shift and Ctrl
        modifiers and update the cursor accordingly.
        
        If shift is pressed, rescale the brush radius and redraw the cursor.
        If ctrl+shift is pressed, rotate and redraw the cursor.

        Args:
            event: A QEvent representing a change in the mouse wheel position.
        """
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

    def canvasPressEvent(self, event):
        """Create initial rubber band geometry based on current mouse position.

        Args:
            event: A QEvent representing the user clicking a mouse button on
                the map canvas.
        """

        # Update reference to active layer
        self.active_layer = self.iface.activeLayer()
        
        # Check for reprojection and if so update flags and attributes
        self.check_coordinate_systems()

        # Set status and color
        if event.button() == Qt.LeftButton:
            self.drawing_mode = 'drawing'
            self.rb.setColor(self.draw_color)

            # If user pressed Ctrl, toggle the merging flag
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ControlModifier:
                self.merging = True
        
        elif event.button() == Qt.RightButton:
            self.drawing_mode = 'erasing'
            self.rb.setColor(self.erase_color)
        
        # Create initial geometry
        point = self.toMapCoordinates(event.pos())
        if self.brush_shape == 'circle':
            self.rb.setToGeometry(self.circle_around_point(point), None) #changed
        elif self.brush_shape == 'wedge':
            self.rb.setToGeometry(self.wedge_around_point(point), None)
        
        # Create previous point and geometry tracker (used in canvasMoveEvent below)
        self.previous_point = point
        self.previous_geometry = self.rb.asGeometry()

    def canvasMoveEvent(self, event):
        """Update the rubber band geometry based on mouse movement.

        To keep track of the different geometries used when calculating the 
        updated geometry of the rubber band, the following variables are used:
            - previous_geometry: the brush geometry around the previous point
            - current_geometry: the brush geometry around the current point
            - new_geometry: the calculated geometry that will be merged with
                the current rubber band to create the updated rubber band.
        
        Args:
            event: A QEvent representing the user moving their mouse across the
                map canvas.
        """
        layer = self.active_layer

        if self.drawing_mode in ('drawing','erasing'):
            # Get current mouse location
            point = self.toMapCoordinates(event.pos())
            
            # Handle drawing with circular brush
            if self.brush_shape == 'circle':
                # Calculate line from previous mouse location
                mouse_move_line = QgsLineString([self.previous_point, point])

                # Calculate buffer distance (could be moved to canvasPressEvent)
                # scale factor is px / mm; as mm (converted to map pixels, then to map units)
                context = QgsRenderContext().fromMapSettings(self.canvas.mapSettings())
                radius = self.brush_radius
                radius *= context.mapToPixel().mapUnitsPerPixel()

                # Calculate new geometry
                new_geometry = QgsGeometry(mouse_move_line).buffer(radius, self.brush_points)

                # Set point tracker to current point
                self.previous_point = point

            # Handle drawing with wedge brush
            elif self.brush_shape == 'wedge':
                # Calculate new geometry
                current_geometry = self.wedge_around_point(point)
                new_geometry = current_geometry.combine(self.previous_geometry).convexHull()

                # Set geometry tracker to current geometry
                self.previous_geometry = current_geometry

            # Set new rubberband geometry
            self.rb.setToGeometry(self.rb.asGeometry().combine(new_geometry))

    def canvasReleaseEvent(self, event):
        """Process the rubber band geometry (simplify, reproject if necessary)
        and then emit it for drawing into the active layer.

        Args:
            event: A QEvent representing the user releasing their mouse button
                after clicking on the map canvas.
        """
        layer = self.active_layer
        current_geometry = self.rb.asGeometry()

        # Reproject the rubberband geometry if necessary
        if self.reprojecting == True:
            new_geometry = QgsGeometry(geom) #have to clone before transforming
            new_geometry.transform(self.t)
        else:
            new_geometry = current_geometry

        # Simplify the rubberband geometry
        # tolerance value is calculated based on brush_radius and brush_points
        # scale factor is px / mm; as mm (converted to map pixels, then to map units)
        # TODO: move this calculation to __init__ above (but have to account
        #       for selecting a new layer with a different CRS)
        context = QgsRenderContext().fromMapSettings(self.canvas.mapSettings())
        radius = self.brush_radius
        radius *= context.mapToPixel().mapUnitsPerPixel()

        tolerance = (2*pi*radius)/(24*self.brush_points)

        new_geometry = new_geometry.simplify(tolerance)
        
        # Emit final geometry
        self.rbFinished.emit(new_geometry)

        # refresh the canvas and reset the rubberband and flags
        self.reset()
        self.canvas.refresh()

        self.drawing_mode = 'inactive'

        self.merging = False
    
    #------------------------------- CALCULATION ------------------------------
    def circle_around_point(self, center, radius=0, num_points=0, map_units=False):
        """Create a circular QgsGeometry centered on a point with a given 
        radius approximated by a number of points.

        Args:
            center: A QgsPointXY indicating the center of the circle.
            radius: An integer or float representing the radius of the circle.
                Defaults to 0, which means that self.brush_radius is used.
            num_points: An integer indicating the number of points to use when
                approximating the circle. Defaults to 0, which means that
                self.brush_points is used.
            map_units: A boolean indicating whether the radius should be
                considered to be in map units. Defaults to False, which means
                that radius is converted from pixels to map units.
        
        Returns:
            A QgsGeometry (of type QGis.Polygon) approximating a circle.

        References:
            - Adapted from https://gis.stackexchange.com/a/69792
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
        """Create a wedge-shaped QgsGeometry around a central point with a 
        given 'radius' (farthest distance from the center to a vertex) and
        rotated by a given angle.

        The wedge geometry matches the image shown in
        :/plugins/brush/resources/redwedge_500x500.png.

        Args:
            center: A QgsPointXY indicating the 'center' of the wedge.
            radius: An integer or float representing the 'radius' of the wedge,
                which corresponds to the longest distance between the center
                and a vertex. Defaults to 0, which means that self.brush_radius
                is used.
            theta: An integer or float representing the angle by which the
                wedge should be rotated.
            map_units: A boolean indicating whether the radius should be
                considered to be in map units. Defaults to False, which means
                that radius is converted from pixels to map units.
        
        Returns:
            A QgsGeometry (of type QGis.Polygon) of a wedge.
        """
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


