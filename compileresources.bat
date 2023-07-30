@echo off
call "C:\OSGeo4W\bin\o4w_env.bat"

@echo on
call "C:\OSGeo4W\apps\Python39\Scripts\pyrcc5.exe" -o resources.py resources.qrc