# Draw By Brush <img src="https://github.com/josephburkhart/Draw-By-Brush/blob/4a16c80b56b941de928ce4b374a5bfd81f71e130/resources/paintbrush.png" width="30">

This plugin adds a new map tool to the QGIS interface, allowing the user to draw polygons as if they were using a brush tool in Paint, Gimp or Photoshop.

## Compatibility
This plugin is compatible with QGIS versions 3.28 and later.

## Setup
This plugin can be downloaded and installed via the built-in Plugin Manager:
1. Determine your QGIS Profile's plugin location by going to Settings > Profiles > Open Active Profile Folder. Within this folder, navigate to `\python\plugins`
2. Clone this repository into that folder
3. Restart QGIS
4. Go to Plugins > Manage and Install Plugins to open the plugin manager
5. In the plugin manager window, go to `Installed` and click the checkbox next to "Draw by Brush" to activate the plugin.

If the plugin does not appear in the final step above, then try installing it from zip:
1. Download this repo as a zip file
2. Go to Plugins > Manage and Install Plugins to open the plugin manager.
3. In the plugin manager window, go to `Install From Zip`, browse to the zip file, and click `Install Plugin`.

## Usage
The plugin adds a new button (icon: <img src="https://github.com/josephburkhart/Draw-By-Brush/blob/4a16c80b56b941de928ce4b374a5bfd81f71e130/resources/paintbrush.png" width="20">) to the interface. When a multipolygon layer is selected, the button can be toggled on to activate the new map tool. Instructions for using the tool can be viewed by hovering over the button.

## Acknowledgements
Many thanks are owed to the Mauro Alberti and Mauro DeDonatis, creators of [beePen](https://plugins.qgis.org/plugins/beePen/), and Takayuki Mizutani, creator of [Bezier Editing](https://plugins.qgis.org/plugins/BezierEditing/) - I studied these plugins extensively when learning how to create my own. Thanks also to Jacky Volpes on the [QGIS-Developer mailing list](https://lists.osgeo.org/mailman/listinfo/qgis-developer), who directed me to these plugins for inspiration.
