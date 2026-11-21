@echo off
rem Start Chatbox. Works from cmd, PowerShell, or by double-clicking.
rem -ExecutionPolicy Bypass applies to this one process only: nothing is changed
rem system-wide, and it avoids the "running scripts is disabled" block.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
if errorlevel 1 pause
