@echo off
:: ============================================================================
:: run_all.bat  —  TB_CPA_Harmonize v1.2  Daily launcher
:: ============================================================================
::
:: HOW TO SCHEDULE WITH WINDOWS TASK SCHEDULER:
:: 1. Open  Task Scheduler  (search in Start menu)
:: 2. Click  "Create Basic Task..."
:: 3. Name:    TB_CPA_Harmonize_daily
:: 4. Trigger: Daily  →  set your desired start time (e.g. 06:00)
:: 5. Action:  "Start a program"
::             Program/script:   C:\...\TB_CPA_Harmonize_v1.2\run_all.bat
::             Start in (optional but recommended):
::                               C:\...\TB_CPA_Harmonize_v1.2\
:: 6. Finish → check "Open the Properties dialog" → Security Options:
::             Tick  "Run whether user is logged on or not"
::             Tick  "Run with highest privileges"  (if network drives are involved)
:: 7. Click OK, enter your Windows password when prompted.
::
:: NOTES:
:: - The lock file (run_all_{HOSTNAME}.lock) prevents a second run from
::   starting while the previous one is still in progress.
:: - Output is written to run_all.log in the same folder.
:: - Edit PROJECTS in run_all_config.py to add / remove data paths.
:: ============================================================================

SET SCRIPT_DIR=%~dp0
SET PYTHON=python
SET LOG_FILE=%SCRIPT_DIR%run_all.log

echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [%DATE% %TIME%] TB_CPA Harmonize pipeline started >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

%PYTHON% "%SCRIPT_DIR%run_all_config.py" >> "%LOG_FILE%" 2>&1

IF %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] Pipeline finished successfully. >> "%LOG_FILE%"
) ELSE (
    echo [%DATE% %TIME%] Pipeline exited with error code %ERRORLEVEL%. >> "%LOG_FILE%"
)
