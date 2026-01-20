@echo off
title Serveur Gestion Locative
echo --- LANCEMENT DU LOGICIEL ---
echo.
echo Ne fermez pas cette fenetre noire tant que vous utilisez le logiciel.
echo.
cd gestion_locative
timeout /t 2 >nul
start http://127.0.0.1:8000/admin/
python manage.py runserver
pause