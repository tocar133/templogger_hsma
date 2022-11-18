#!/bin/bash

user=$(logname)
script_pfad=$(realpath -s "$0")
script_ordner_pfad=$(dirname "$script_pfad")

echo "########################################################################"
echo "Repository klonen"
git clone https://github.com/tocar133/templogger_hsma.git Templogger
if [ $? -eq 0 ]; then
    echo "Repository wurde geklont"
else
    echo "Repository wurde nicht geklont"
fi
#read a

echo "########################################################################"
echo "Desktop Shortcut erstellen"
if test -f "/home/$user/Desktop/Templogger.desktop"; then
    echo "/home/$user/Desktop/Templogger.desktop existiert bereits."
else
    echo "[Desktop Entry]
    Type=Application
    Encoding=UTF-8
    Name=Templogger starten
    Exec=/usr/bin/python3 $script_ordner_pfad/Templogger/templogger.py
    Terminal=true
    X-KeepTerminal=true" >> "/home/$user/Desktop/Templogger.desktop"
    if [ $? -eq 0 ]; then
        echo "Desktop Shortcut wurde erstellt"
    else
        echo "Desktop Shortcut wurde nicht erstellt"
    fi
fi
#read a

echo "########################################################################"
echo "Templogger Autostart einrichten"
if [ -d "/home/$user/.config/autostart" ]; then
    echo "/home/$user/.config/autostart existiert bereits"
else
    mkdir "/home/$user/.config/autostart"
    echo "autostartordner erstellt"
fi
if test -f "/home/$user/.config/autostart/Templogger.desktop"; then
    echo "/home/$user/.config/autostart/Templogger.desktop existiert bereits."
else
    cp "/home/$user/Desktop/Templogger.desktop" "/home/$user/.config/autostart/Templogger.desktop"
    if [ $? -eq 0 ]; then
        echo "Templogger Autostart wurde eingerichtet"
    else
        echo "Templogger Autostart wurde nicht eingerichtet"
    fi
fi
#read a

echo "########################################################################"
echo "Tastaturlayout kopieren"
if [ -d "/home/$user/.matchbox" ]; then
    echo "/home/$user/.matchbox existiert bereits"
else
    mkdir "/home/$user/.matchbox"
    echo "tastaturordner erstellt"
fi
if test -f "/home/$user/.matchbox/keyboard.xml"; then
    echo "/home/$user/.matchbox/keyboard.xml existiert bereits."
else
    cp "Templogger/keyboard.xml" "/home/$user/.matchbox"
    if [ $? -eq 0 ]; then
        echo "Tastaturlayout wurde kopieren"
    else
        echo "Tastaturlayout wurde nicht kopieren"
    fi
fi
#read a

echo "########################################################################"
echo "update startet"
apt-get update
if [ $? -eq 0 ]; then
    echo "system wurde geupdatet"
else
    echo "system wurde nicht geupdatet"
fi
#read a

echo "########################################################################"
echo "system upgrade startet"
apt-get -y upgrade
if [ $? -eq 0 ]; then
    echo "system wurde geupgradet"
else
    echo "system wurde nicht geupgradet"
fi
#read a

echo "########################################################################"
echo "matplotlib installieren"
pip install matplotlib
if [ $? -eq 0 ]; then
    echo "matplotlib wurde installieren"
else
    echo "matplotlib wurde nicht installieren"
fi
#read a

echo "########################################################################"
echo "numpy upgrade"
pip install numpy --upgrade
if [ $? -eq 0 ]; then
    echo "numpy wurde geupgradet"
else
    echo "numpy wurde nicht geupgradet"
fi
#read a

echo "########################################################################"
echo "libatlas-base-dev installieren"
apt-get -y install libatlas-base-dev
if [ $? -eq 0 ]; then
    echo "libatlas-base-dev wurde installieren"
else
    echo "libatlas-base-dev wurde nicht installieren"
fi
#read a

echo "########################################################################"
echo "python3-pil.imagetk installieren"
apt-get -y install python3-pil.imagetk
if [ $? -eq 0 ]; then
    echo "python3-pil.imagetk wurde installieren"
else
    echo "python3-pil.imagetk wurde nicht installieren"
fi
#read a

echo "########################################################################"
echo "adafruit-blinka installieren"
pip3 install adafruit-blinka
if [ $? -eq 0 ]; then
    echo "adafruit_blinka wurde installieren"
else
    echo "adafruit_blinka wurde nicht installieren"
fi
#read a

echo "########################################################################"
echo "adafruit-circuitpython-max31865 installieren"
pip3 install adafruit-circuitpython-max31865
if [ $? -eq 0 ]; then
    echo "adafruit-circuitpython-max31865 wurde installieren"
else
    echo "adafruit-circuitpython-max31865 wurde nicht installieren"
fi
#read a

echo "########################################################################"
echo "adafruit-extended-bus installieren"
pip3 install adafruit-extended-bus
if [ $? -eq 0 ]; then
    echo "adafruit-extended-bus wurde installieren"
else
    echo "adafruit-extended-bus wurde nicht installieren"
fi
#read a

echo "########################################################################"
echo "matchbox-keyboard installieren"
apt-get install matchbox-keyboard
if [ $? -eq 0 ]; then
    echo "keyboard wurde installieren"
else
    echo "keyboard wurde nicht installieren"
fi
#read a

echo "########################################################################"
echo "x11vnc installieren"
apt-get -y install x11vnc
if [ $? -eq 0 ]; then
    echo "x11vnc wurde installieren"
else
    echo "x11vnc wurde nicht installieren"
fi
#read a

echo "########################################################################"
echo "x11vnc passwort setzen"
if [ -d "/home/$user/.vnc" ]; then
    echo "/home/$user/.vnc existiert bereits"
else
    mkdir "/home/$user/.vnc"
    echo "benutzer .vnc ordner erstellt"
fi
if test -f "/home/$user/.vnc/passwd"; then
    echo "/home/$user/.vnc/passwd existiert bereits."
else
    touch "/home/$user/.vnc/passwd"
    x11vnc -storepasswd 'Templogger' "/home/$user/.vnc/passwd"
    chmod 644 "/home/$user/.vnc/passwd"
    if [ $? -eq 0 ]; then
        echo "x11vnc passwort wurde gesetzen"
    else
        echo "x11vnc passwort wurde nicht setzen"
    fi
fi
#read a

echo "########################################################################"
echo "Remote Desktop Services Autostart einrichten"
if test -f "/home/$user/.config/autostart/x11vnc.desktop"; then
    echo "/home/$user/.config/autostart/x11vnc.desktop existiert bereits."
else
    echo "[Desktop Entry]
    Type=Application
    Name=X11VNC
    Exec=x11vnc -usepw -forever -display :0
    StartupNotify=false" >> "/home/$user/.config/autostart/x11vnc.desktop"
    if [ $? -eq 0 ]; then
        echo "Remote Desktop Services Autostart wurde eingerichten"
    else
        echo "Remote Desktop Services Autostart wurde nicht eingerichten"
    fi
fi
#read a

echo "########################################################################"
echo "SPI einschalten"
echo "dtparam=spi=on" >> '/boot/config.txt'
if [ $? -eq 0 ]; then
    echo "SPI wurde eingeschaltet"
else
    echo "SPI wurde nicht eingeschaltet"
fi
#read a

echo "########################################################################"
echo "SSH Port zu 3756 aendern"
echo 'Port 3756' >> '/etc/ssh/sshd_config'
if [ $? -eq 0 ]; then
    echo "SSH Port wurde geaendert"
else
    echo "SSH Port wurde nicht geaendert"
fi
#read a

echo "########################################################################"
echo "Fertig, bitte druecke Sie Enter zum neustarten"
echo "########################################################################"
read a

reboot