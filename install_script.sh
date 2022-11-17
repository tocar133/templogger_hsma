#!/bin/bash

user_pfad=$(eval echo ~$user)
keyboard_ordner = "/.matchbox"
templogger_shortcut = "/Templogger.desktop"
autostart_ordner='/.config/autostart'
remote_desktop_shortcut='/x11vnc.desktop'
remote_desktop_ordner='/.vnc'
remote_desktop_passwortdatei='/passwd'

echo "########################################################################"
echo "Repository klonen"
echo "########################################################################"
git clone https://github.com/tocar133/templogger_hsma Templogger
echo "klonen fertig"
#read a

echo "########################################################################"
echo "Desktop Shortcut erstellen"
echo "########################################################################"
echo "[Desktop Entry]
Type=Application
Encoding=UTF-8
Name=Templogger starten
Exec=/usr/bin/python3 $user_pfad/Templogger/templogger.py
Terminal=true
X-KeepTerminal=true" >> "$user_pfad/Desktop$templogger_shortcut"
echo "wurde erstellt"
#read a

echo "########################################################################"
echo "Templogger Autostart einrichten"
echo "########################################################################"
mkdir "$user_pfad$autostart_ordner"
cp "$templogger_shortcut" "$user_pfad$autostart_ordner$templogger_shortcut"
chmod +x "$user_pfad$autostart_ordner$templogger_shortcut"
echo "Templogger Autostart wurde eingerichtet"
#read a

echo "########################################################################"
echo "update wurde startet"
echo "########################################################################"
sudo apt-get update
echo "update fertig"
#read a

echo "########################################################################"
echo "upgrade wurde startet"
echo "########################################################################"
sudo apt-get -y upgrade
echo "upgrade fertig"
#read a

echo "########################################################################"
echo "install matplotlib"
echo "########################################################################"
sudo pip install matplotlib
echo "wurde installiert"
#read a

echo "########################################################################"
echo "upgrade numpy"
echo "########################################################################"
sudo pip install numpy --upgrade
echo "upgrade fertig"
#read a

echo "########################################################################"
echo "install libatlas-base-dev"
echo "########################################################################"
sudo apt-get -y install libatlas-base-dev
echo "wurde installiert"
#read a

echo "########################################################################"
echo "install python3-pil.imagetk"
echo "########################################################################"
sudo apt-get -y install python3-pil.imagetk
echo "wurde installiert"
#read a

echo "########################################################################"
echo "install adafruit-blinka"
echo "########################################################################"
sudo pip3 install adafruit-blinka
echo "wurde installiert"
#read a

echo "########################################################################"
echo "upgrade adafruit_blinka"
echo "########################################################################"
sudo pip3 install --upgrade adafruit_blinka
echo "upgrade fertig"
#read a

echo "########################################################################"
echo "install adafruit-circuitpython-max31865"
echo "########################################################################"
sudo pip3 install adafruit-circuitpython-max31865
echo "wurde installiert"
#read a

echo "########################################################################"
echo "install adafruit-extended-bus"
echo "########################################################################"
sudo pip3 install adafruit-extended-bus
echo "wurde installiert"
#read a

echo "########################################################################"
echo "install matchbox-keyboard"
echo "########################################################################"
sudo apt-get install matchbox-keyboard
mkdir "$user_pfad$keyboard_ordner"
echo "wurde installiert"
#read a

echo "########################################################################"
echo "install x11vnc"
echo "########################################################################"
sudo apt-get -y install x11vnc
echo "wurde installiert"
#read a

echo "########################################################################"
echo "x11vnc passwort setzen"
echo "########################################################################"
mkdir "$user_pfad$remote_desktop_ordner"
touch "$user_pfad$remote_desktop_ordner$remote_desktop_passwortdatei"
x11vnc -storepasswd 'Templogger' "$user_pfad$remote_desktop_ordner$remote_desktop_passwortdatei"
echo "passwort wurde gesetzt"
#read a

echo "########################################################################"
echo "Schreibe Datei zum einschalten des Autostarts des Remote Desktop Services"
echo "########################################################################"
echo "[Desktop Entry]
Type=Application
Name=X11VNC
Exec=x11vnc -usepw -forever -display :0
StartupNotify=false" >> "$user_pfad$autostart_ordner$remote_desktop_shortcut"
echo "schreiben fertig"
#read a

echo "########################################################################"
echo "SPI wird einschalten"
echo "########################################################################"
sudo echo "dtparam=spi=on" >> '/boot/config.txt'
#dtoverlay=spi1-3cs" >> '/boot/config.txt'
echo "SPI wurde eingeschaltet"
#read a

echo "########################################################################"
echo "SSH Port wird zu 3756"
echo "########################################################################"
sudo echo 'Port 3756' >> '/etc/ssh/sshd_config'
echo "SSH Port wurde gewechselt"
#read a

#echo "########################################################################"
#echo "Initialisiere matplotlib"
#echo "########################################################################"
#sudo python3 -c "import matplotlib"
#echo "matplotlib wurde initialisiert"
#read a

echo "########################################################################"
echo "Fertig, bitte drücke Sie eine Tasten zum neustarten"
echo "########################################################################"
read a

sudo reboot