@echo off
echo Installation des dependances...
python -m pip install --upgrade pip
python -m pip install minecraft-launcher-lib pyinstaller

echo.
echo Creation de l'executable avec icone...
python -m PyInstaller --onefile --noconsole --icon="icone.ico" --add-data "icone.ico;." --name="Manille et Mathis" launcher.py

echo.
echo Termine ! Votre fichier "Manille et Mathis.exe" se trouve dans le dossier "dist".
pause
