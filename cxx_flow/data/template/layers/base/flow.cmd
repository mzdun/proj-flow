@rem Copyright (c) 2025 Marcin Zdun
@rem This code is licensed under MIT license (see LICENSE for details)

@echo off
if "%OS%"=="Windows_NT" setlocal
set DIRNAME=%~dp0
if "%DIRNAME%"=="" set DIRNAME=.

python "%DIRNAME%/.flow/flow.py" %*
