@ECHO OFF
REM Forward workspace-root Gradle invocations to the MagicSpells project.
SETLOCAL
SET "ROOT=%~dp0"
CD /D "%ROOT%MagicSpells"
CALL gradlew.bat %*
EXIT /B %ERRORLEVEL%
