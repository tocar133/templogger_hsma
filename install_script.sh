#!/bin/bash

user=$(logname)
script_pfad=$(realpath -s "$0")
script_ordner_pfad=$(dirname "$script_pfad")

#echo "########################################################################"
#echo "Repository klonen"
#sudo git clone https://github.com/tocar133/templogger_hsma.git "$script_ordner_pfad/Templogger"
#if [ $? -eq 0 ]; then
#    echo "Repository wurde geklont"
#    sudo chown -R "$user":"$user" "$script_ordner_pfad/Templogger"
#else
#    echo "Repository wurde nicht geklont"
#fi
#read a

echo "########################################################################"
echo "Desktop Shortcut erstellen"
if test -f "/home/$user/Desktop/Templogger.desktop"; then
    echo "/home/$user/Desktop/Templogger.desktop existiert bereits."
else
    #Exec=lxterminal -t "Templogger Konsole" -e python3 $script_ordner_pfad/Templogger/templogger.py
    sudo echo "[Desktop Entry]
    Type=Application
    Encoding=UTF-8
    Name=Templogger starten
    Exec=lxterminal -t 'Templogger Konsole' -e python3 $script_ordner_pfad/templogger.py
    Terminal=true
    X-KeepTerminal=true" >> "/home/$user/Desktop/Templogger.desktop"
    if [ $? -eq 0 ]; then
        sudo chown "$user":"$user" "/home/$user/Desktop/Templogger.desktop"
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
    sudo mkdir "/home/$user/.config/autostart"
    echo "autostartordner erstellt"
fi
if test -f "/home/$user/.config/autostart/Templogger.desktop"; then
    echo "/home/$user/.config/autostart/Templogger.desktop existiert bereits."
else
    sudo cp "/home/$user/Desktop/Templogger.desktop" "/home/$user/.config/autostart/Templogger.desktop"
    if [ $? -eq 0 ]; then
        sudo chown -R "$user":"$user" "/home/$user/.config/autostart"
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
    sudo mkdir "/home/$user/.matchbox"
    echo "tastaturordner erstellt"
fi
if test -f "/home/$user/.matchbox/keyboard.xml"; then
    echo "/home/$user/.matchbox/keyboard.xml existiert bereits."
else
    #sudo cp "$script_ordner_pfad/Templogger/keyboard.xml" "/home/$user/.matchbox"
    sudo cp "$script_ordner_pfad/keyboard.xml" "/home/$user/.matchbox"
    if [ $? -eq 0 ]; then
        sudo chown -R "$user":"$user" "/home/$user/.matchbox"
        echo "Tastaturlayout wurde kopiert"
    else
        echo "Tastaturlayout wurde nicht kopiert"
    fi
fi
#read a

echo "########################################################################"
echo "update startet"
sudo apt-get update
if [ $? -eq 0 ]; then
    echo "system wurde geupdatet"
else
    echo "system wurde nicht geupdatet"
fi
#read a

echo "########################################################################"
echo "system upgrade startet"
sudo sudo apt-get -y upgrade
if [ $? -eq 0 ]; then
    echo "system wurde geupgradet"
else
    echo "system wurde nicht geupgradet"
fi
#read a

echo "########################################################################"
echo "matplotlib installieren"
sudo pip install matplotlib
if [ $? -eq 0 ]; then
    echo "matplotlib wurde installiert"
else
    echo "matplotlib wurde nicht installiert"
fi
#read a

echo "########################################################################"
echo "numpy upgrade"
sudo pip install numpy --upgrade
if [ $? -eq 0 ]; then
    echo "numpy wurde geupgradet"
else
    echo "numpy wurde nicht geupgradet"
fi
#read a

echo "########################################################################"
echo "libatlas-base-dev installieren"
sudo apt-get -y install libatlas-base-dev
if [ $? -eq 0 ]; then
    echo "libatlas-base-dev wurde installiert"
else
    echo "libatlas-base-dev wurde nicht installiert"
fi
#read a

echo "########################################################################"
echo "python3-pil.imagetk installieren"
sudo apt-get -y install python3-pil.imagetk
if [ $? -eq 0 ]; then
    echo "python3-pil.imagetk wurde installiert"
else
    echo "python3-pil.imagetk wurde nicht installiert"
fi
#read a

echo "########################################################################"
echo "adafruit-blinka installieren"
sudo pip3 install adafruit-blinka
if [ $? -eq 0 ]; then
    echo "adafruit_blinka wurde installiert"
else
    echo "adafruit_blinka wurde nicht installiert"
fi
#read a

echo "########################################################################"
echo "adafruit-circuitpython-max31865 installieren"
sudo pip3 install adafruit-circuitpython-max31865
if [ $? -eq 0 ]; then
    echo "adafruit-circuitpython-max31865 wurde installiert"
else
    echo "adafruit-circuitpython-max31865 wurde nicht installiert"
fi
#read a

echo "########################################################################"
echo "adafruit-extended-bus installieren"
sudo pip3 install adafruit-extended-bus
if [ $? -eq 0 ]; then
    echo "adafruit-extended-bus wurde installiert"
else
    echo "adafruit-extended-bus wurde nicht installiert"
fi
#read a

echo "########################################################################"
echo "matchbox-keyboard installieren"
sudo apt-get -y install matchbox-keyboard
if [ $? -eq 0 ]; then
    echo "keyboard wurde installiert"
else
    echo "keyboard wurde nicht installiert"
fi
#read a

echo "########################################################################"
echo "x11vnc installieren"
sudo apt-get -y install x11vnc
if [ $? -eq 0 ]; then
    echo "x11vnc wurde installiert"
else
    echo "x11vnc wurde nicht installiert"
fi
#read a

echo "########################################################################"
echo "x11vnc passwort setzen"
if [ -d "/home/$user/.vnc" ]; then
    echo "/home/$user/.vnc existiert bereits"
else
    sudo mkdir "/home/$user/.vnc"
    echo "benutzer .vnc ordner erstellt"
fi
if test -f "/home/$user/.vnc/passwd"; then
    echo "/home/$user/.vnc/passwd existiert bereits."
else
    sudo touch "/home/$user/.vnc/passwd"
    sudo x11vnc -storepasswd 'Templogger' "/home/$user/.vnc/passwd"
    if [ $? -eq 0 ]; then
        sudo chown -R "$user":"$user" "/home/$user/.vnc"
        echo "x11vnc passwort wurde gesetzt"
    else
        echo "x11vnc passwort wurde nicht gesetzt"
    fi
fi
#read a

echo "########################################################################"
echo "Remote Desktop Services Autostart einrichten"
if test -f "/home/$user/.config/autostart/x11vnc.desktop"; then
    echo "/home/$user/.config/autostart/x11vnc.desktop existiert bereits."
else
    sudo echo "[Desktop Entry]
    Type=Application
    Name=X11VNC
    Exec=x11vnc -usepw -forever -display :0
    StartupNotify=false" >> "/home/$user/.config/autostart/x11vnc.desktop"
    if [ $? -eq 0 ]; then
        sudo chown -R "$user":"$user" "/home/$user/.config/autostart"
        echo "Remote Desktop Services Autostart wurde eingerichtet"
    else
        echo "Remote Desktop Services Autostart wurde nicht eingerichtet"
    fi
fi
#read a

echo "########################################################################"
echo "SPI einschalten"
sudo echo "dtparam=spi=on" >> '/boot/config.txt'
if [ $? -eq 0 ]; then
    echo "SPI wurde eingeschaltet"
else
    echo "SPI wurde nicht eingeschaltet"
fi
#read a

echo "########################################################################"
echo "SSH Port zu 3756 aendern"
sudo echo 'Port 3756' >> '/etc/ssh/sshd_config'
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