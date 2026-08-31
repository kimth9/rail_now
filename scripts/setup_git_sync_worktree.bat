@echo off
setlocal enabledelayedexpansion
rem Reference: ../../project standard guide, section 16.2 (git sync protocol)
rem Creates persistent sibling worktrees PROJECT_main_sync / PROJECT_reports_sync
rem as orphan branches (main-sync / reports-sync). Run from the project root
rem after "git init" and the first commit (section 5.1).

if "%~1"=="" (
    echo Usage: setup_git_sync_worktree.bat PROJECT_NAME
    exit /b 1
)

set PROJECT=%~1

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Not a git repository here. Run "git init" first.
    exit /b 1
)

if exist "..\%PROJECT%_main_sync" (
    echo [SKIP] ..\%PROJECT%_main_sync already exists
) else (
    git worktree add --detach "..\%PROJECT%_main_sync"
    pushd "..\%PROJECT%_main_sync"
    git checkout --orphan main-sync
    popd
    echo [DONE] ..\%PROJECT%_main_sync  branch: main-sync
)

if exist "..\%PROJECT%_reports_sync" (
    echo [SKIP] ..\%PROJECT%_reports_sync already exists
) else (
    git worktree add --detach "..\%PROJECT%_reports_sync"
    pushd "..\%PROJECT%_reports_sync"
    git checkout --orphan reports-sync
    popd
    echo [DONE] ..\%PROJECT%_reports_sync  branch: reports-sync
)

echo.
echo Next: copy essential files into each worktree, then commit and push:
echo   git push origin main-sync:main
echo   git push origin reports-sync:reports
echo Details: ../../project standard guide, section 16
endlocal
