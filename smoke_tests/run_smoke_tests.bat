@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ------------------------------------------------------------
REM JSON-LOOM smoke tests runner
REM ------------------------------------------------------------

pushd "%~dp0"

set "PY=python"
set "LOOM=%PY% ..\jsonloom.py"
set "RESULTS=results"
set "LOG=%RESULTS%\smoke_tests.log"

REM Prep results folder + fresh log
mkdir "%RESULTS%" 2>nul
del /q "%LOG%" 2>nul

REM ---- sanity: python available?
%PY% -c "import sys;print(sys.version)" 1>nul 2>&1
if errorlevel 1 (
  echo Python not found on PATH. Aborting. >"%LOG%"
  type "%LOG%"
  popd
  exit /b 2
)

REM ---- presence checks ----
for %%I in (
  preprocessor_default_alias_id.json
  preprocessor_field_qualified.json
  preprocessor_whitespace_tolerance.json
  preprocessor_strict_projection.json
  preprocessor_object_map_imports.json
  preprocessor_missing_record.json
  preprocessor_unknown_alias.json
  preprocessor_circular_reference.json
  preprocessor_datalarge.json
  preprocessor_inventory_array.json
  preprocessor_binary_copy.json
) do (
  if not exist "%%~I" (
    echo Missing input: %%~I >"%LOG%"
    type "%LOG%"
    popd
    exit /b 3
  )
)

REM ------------------ define test table ----------------------
REM Format: label|command|should_fail(0/1)

REM --- expected to pass ------------
set "T1=default_alias_id|%LOOM% preprocessor_default_alias_id.json|0"
set "T2=field_qualified|%LOOM% preprocessor_field_qualified.json|0"
set "T3=whitespace_tolerance|%LOOM% preprocessor_whitespace_tolerance.json|0"
set "T4=alias_warn|%LOOM% preprocessor_strict_projection.json|0"
set "T5=object_map_imports|%LOOM% preprocessor_object_map_imports.json|0"
set "T6=order_items_array|%LOOM% preprocessor_datalarge.json|0"
set "T7=inventory_array|%LOOM% preprocessor_inventory_array.json|0"
set "T8=binary_copy|%LOOM% preprocessor_binary_copy.json|0"

REM --- expected to fail ------------
set "T9=alias_strict|%LOOM% preprocessor_strict_projection.json --strict-projection|1"
set "T10=missing_record|%LOOM% preprocessor_missing_record.json|1"
set "T11=unknown_alias|%LOOM% preprocessor_unknown_alias.json|1"
set "T12=circular_reference|%LOOM% preprocessor_circular_reference.json|1"

REM ------------------ run tests ------------------------------
(
  echo.
  echo JSON-LOOM Smoke Tests
  echo.
  echo ============================================================

  set "PASS_COUNT=0"
  set "FAIL_COUNT=0"

  for /L %%N in (1,1,12) do (
    for /f "tokens=1,2,3 delims=|" %%A in ("!T%%N!") do (
      set "LABEL=%%~A"
      set "CMD=%%~B"
      set "EXPECT_FAIL=%%~C"

      echo.
      echo.
      echo !LABEL!
      echo ------------------------------------------------------------
      echo   Cleaning old outputs...
      del /q "*.compiled.json" "*.compiled.bson" 2>nul

      echo   Running: !CMD!
      call !CMD!
      set "ERR=!ERRORLEVEL!"

      for %%F in (*.compiled.json) do move /y "%%F" "%RESULTS%\!LABEL!.compiled.json" >nul
      for %%F in (*.compiled.bson) do move /y "%%F" "%RESULTS%\!LABEL!.compiled.bson" >nul

      if "!EXPECT_FAIL!"=="1" (
        if not "!ERR!"=="0" (
          echo.
          echo   ^> OK ^(expected failure^)
          set /a PASS_COUNT+=1
        ) else (
          echo.
          echo   ^> FAIL ^(expected failure but command succeeded^)
          set /a FAIL_COUNT+=1
        )
      ) else (
        if "!ERR!"=="0" (
          echo.
          echo   ^> OK
          set /a PASS_COUNT+=1
        ) else (
          echo.
          echo   ^> FAIL ^(exitcode !ERR!^)
          set /a FAIL_COUNT+=1
        )
      )
      echo.
    )
  )

  echo.
  echo ************************************************************
  echo RESULTS
  echo ------------------------------------------------------------
  echo Passed: !PASS_COUNT!
  echo Failed: !FAIL_COUNT!
  echo ************************************************************
) 1>>"%LOG%" 2>&1

type "%LOG%"

set "RC=0"
for /f "tokens=2 delims=:" %%X in ('findstr /R /C:"^Failed:" "%LOG%"') do (
  for /f "delims= " %%Y in ("%%~X") do (
    if not "%%~Y"=="0" set "RC=1"
  )
)

popd
exit /b %RC%
