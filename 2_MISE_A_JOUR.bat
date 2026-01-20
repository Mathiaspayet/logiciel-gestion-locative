@echo off
title Mise a jour Base de Donnees
echo --- MISE A JOUR DE LA BASE DE DONNEES ---
echo.
cd gestion_locative
python manage.py makemigrations
python manage.py migrate
echo.
echo ---------------------------------------------------
echo Tout est a jour ! Vous pouvez fermer cette fenetre.
echo ---------------------------------------------------
pause