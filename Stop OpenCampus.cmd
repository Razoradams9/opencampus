@echo off
rem Stops OpenCampus. Your data is kept.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
