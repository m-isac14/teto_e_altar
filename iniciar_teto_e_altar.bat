@echo off
title Teto & Altar - Gestao Financeira Casamento e Apartamento (Isac)
cd /d "%~dp0"
echo ========================================================
echo   INICIANDO TETO & ALTAR (STREAMLIT + SUPABASE)
echo ========================================================
echo.
echo Abrindo painel no navegador (http://localhost:8501)...
"%~dp0venv\Scripts\python.exe" -m streamlit run app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocorreu um erro ao iniciar diretamente. Tentando via activate...
    call "%~dp0venv\Scripts\activate.bat"
    python -m streamlit run app.py
)
pause
