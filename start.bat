@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYW="
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PYW=%~dp0.venv\Scripts\pythonw.exe"
if not defined PYW if exist "%~dp0venv\Scripts\pythonw.exe" set "PYW=%~dp0venv\Scripts\pythonw.exe"

if not defined PYW (
  for /f "delims=" %%I in ('where pythonw 2^>nul') do (
    set "PYW=%%I"
    goto :have_py
  )
)

:have_py
if not defined PYW (
  for /f "delims=" %%I in ('where python 2^>nul') do (
    set "PYW=%%I"
    goto :have_py2
  )
)

:have_py2
if not defined PYW (
  echo [Py 工具集] 未找到 Python。
  echo 请安装 Python 并加入 PATH，或在本目录创建 .venv 后重试。
  pause
  exit /b 1
)

if not exist "%~dp0main_app.py" (
  echo [Py 工具集] 未找到 main_app.py
  pause
  exit /b 1
)

start "" "%PYW%" "%~dp0main_app.py"
exit /b 0
