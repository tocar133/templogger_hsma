#!/bin/bash

user=$(logname)
script_pfad=$(realpath -s "$0")
script_ordner_pfad=$(dirname "$script_pfad")

declare -i fehler=0

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
        fehler=$(( fehler + 1 ))
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
        fehler=$(( fehler + 1 ))
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
        fehler=$(( fehler + 1 ))
    fi
fi
#read a

echo "########################################################################"
echo "Desktop Hintergrund und Schriftfarbe aendern"

if [ -d "/home/$user/.config/pcmanfm" ]; then
    echo "/home/$user/.config/pcmanfm existiert bereits"
else
    sudo mkdir "/home/$user/.config/pcmanfm"
    echo "pcmanfm Ordner erstellt"
fi
if [ -d "/home/$user/.config/pcmanfm/LXDE-pi" ]; then
    echo "/home/$user/.config/pcmanfm/LXDE-pi existiert bereits"
else
    sudo mkdir "/home/$user/.config/pcmanfm/LXDE-pi"
    echo "LXDE-pi Ordner erstellt"
fi
if test -f "/home/$user/.config/pcmanfm/LXDE-pi/desktop-items-0.conf"; then
    echo "/home/$user/.config/pcmanfm/LXDE-pi/desktop-items-0.conf existiert bereits."
else
    sudo echo "[*]
wallpaper_mode=crop
wallpaper_common=1
wallpaper=/usr/share/rpd-wallpaper/clouds.jpg
desktop_bg=#d6d3de
desktop_fg=#e8e8e8
desktop_shadow=#d6d3de
desktop_font=PibotoLt 12
show_wm_menu=0
sort=mtime;ascending;
show_documents=0
show_trash=1
show_mounts=1

" >> "/home/$user/.config/pcmanfm/LXDE-pi/desktop-items-0.conf"
    if [ $? -eq 0 ]; then
        sudo chown "$user":"$user" "/home/$user/.config/pcmanfm/LXDE-pi/desktop-items-0.conf"
        echo "pcmanfm Desktop config Datei erstellt"
    else
        echo "pcmanfm Desktop config Datei wurde nicht erstellt"
        fehler=$(( fehler + 1 ))
    fi
fi

sed -i '2s;.*;wallpaper_mode=fit;' "/home/$user/.config/pcmanfm/LXDE-pi/desktop-items-0.conf"
if [ $? -eq 0 ]; then
    echo "Hintergrund Darstellungsmode wurde geaendert"
else
    echo "Hintergrund Darstellungsmode wurde nicht geaendert"
    fehler=$(( fehler + 1 ))
fi

sed -i "4s;.*;wallpaper=$script_ordner_pfad/Bilder/Desktop_Background.svg;" "/home/$user/.config/pcmanfm/LXDE-pi/desktop-items-0.conf"
if [ $? -eq 0 ]; then
    echo "Hintergrundbild wurde geaendert"
else
    echo "Hintergrundbild wurde nicht geaendert"
    fehler=$(( fehler + 1 ))
fi

sed -i '5s;.*;desktop_bg=#FFFFFF;' "/home/$user/.config/pcmanfm/LXDE-pi/desktop-items-0.conf"
if [ $? -eq 0 ]; then
    echo "Desktophintergrundfarbe wurde geaendert"
else
    echo "Desktophintergrundfarbe wurde nicht geaendert"
    fehler=$(( fehler + 1 ))
fi

sed -i '6s;.*;desktop_fg=#000000;' "/home/$user/.config/pcmanfm/LXDE-pi/desktop-items-0.conf"
if [ $? -eq 0 ]; then
    echo "Desktop Schriftfarbe wurde geaendert"
else
    echo "Desktop Schriftfarbe wurde nicht geaendert"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "Boot Logo aendern"

sudo cp "$script_ordner_pfad/Bilder/boot_logo.png" /usr/share/plymouth/themes/pix/splash.png
if [ $? -eq 0 ]; then
    echo "Boot Logo wurde geaendert"
else
    echo "Boot Logo wurde nicht geaendert"
    fehler=$(( fehler + 1 ))
fi
#read a


echo "########################################################################"
echo "update startet"
sudo apt-get update
if [ $? -eq 0 ]; then
    echo "system wurde geupdatet"
else
    echo "system wurde nicht geupdatet"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "system upgrade startet"
sudo sudo apt-get -y upgrade
if [ $? -eq 0 ]; then
    echo "system wurde geupgradet"
else
    echo "system wurde nicht geupgradet"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "matplotlib installieren"
sudo pip install matplotlib
if [ $? -eq 0 ]; then
    echo "matplotlib wurde installiert"
else
    echo "matplotlib wurde nicht installiert"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "numpy upgrade"
sudo pip install numpy --upgrade
if [ $? -eq 0 ]; then
    echo "numpy wurde geupgradet"
else
    echo "numpy wurde nicht geupgradet"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "libatlas-base-dev installieren"
sudo apt-get -y install libatlas-base-dev
if [ $? -eq 0 ]; then
    echo "libatlas-base-dev wurde installiert"
else
    echo "libatlas-base-dev wurde nicht installiert"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "python3-pil.imagetk installieren"
sudo apt-get -y install python3-pil.imagetk
if [ $? -eq 0 ]; then
    echo "python3-pil.imagetk wurde installiert"
else
    echo "python3-pil.imagetk wurde nicht installiert"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "adafruit-blinka installieren"
sudo pip3 install adafruit-blinka
if [ $? -eq 0 ]; then
    echo "adafruit_blinka wurde installiert"
else
    echo "adafruit_blinka wurde nicht installiert"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "adafruit-circuitpython-max31865 installieren"
sudo pip3 install adafruit-circuitpython-max31865
if [ $? -eq 0 ]; then
    echo "adafruit-circuitpython-max31865 wurde installiert"
else
    echo "adafruit-circuitpython-max31865 wurde nicht installiert"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "adafruit-extended-bus installieren"
sudo pip3 install adafruit-extended-bus
if [ $? -eq 0 ]; then
    echo "adafruit-extended-bus wurde installiert"
else
    echo "adafruit-extended-bus wurde nicht installiert"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "matchbox-keyboard installieren"
sudo apt-get -y install matchbox-keyboard
if [ $? -eq 0 ]; then
    echo "keyboard wurde installiert"
else
    echo "keyboard wurde nicht installiert"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "x11vnc installieren"
sudo apt-get -y install x11vnc
if [ $? -eq 0 ]; then
    echo "x11vnc wurde installiert"
else
    echo "x11vnc wurde nicht installiert"
    fehler=$(( fehler + 1 ))
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
        fehler=$(( fehler + 1 ))
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
        fehler=$(( fehler + 1 ))
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
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "SSH einschalten"
sudo touch /boot/ssh
if [ $? -eq 0 ]; then
    echo "SSH wurde eingeschaltet"
else
    echo "SSH wurde nicht eingeschaltet"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "SSH Port zu 3756 aendern"
sudo echo 'Port 3756' >> '/etc/ssh/sshd_config'
if [ $? -eq 0 ]; then
    echo "SSH Port wurde geaendert"
else
    echo "SSH Port wurde nicht geaendert"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "Display config"
sudo echo "hdmi_group=2
hdmi_mode=87
hdmi_cvt 1280 800 60 6 0 0 0
hdmi_drive=1" >> '/boot/config.txt'
if [ $? -eq 0 ]; then
    echo "Konfiguration fuer Display erfolgreich"
else
    echo "Konfiguration fuer Display nicht erfolgreich"
    fehler=$(( fehler + 1 ))
fi
#read a

echo "########################################################################"
echo "Tool fuer Display Helligkeit installieren"
git clone https://github.com/waveshare/RPi-USB-Brightness "$script_ordner_pfad/RPi-USB-Brightness"
if [ $? -eq 0 ]; then
    echo "Helligkeitstool wurde heruntergeladen"

    cd "$script_ordner_pfad/RPi-USB-Brightness/32/desktop"
    sudo "./install.sh"
    if [ $? -eq 0 ]; then
        sudo rm -r "$script_ordner_pfad/RPi-USB-Brightness"
        echo "Helligkeitstool wurde installiert"
    else
        echo "Helligkeitstool wurde nicht installiert"
        fehler=$(( fehler + 1 ))
    fi
else
    echo "Herunterladen des Helligkeitstool fehlgeschlagen"
    fehler=$(( fehler + 1 ))
fi
cd "$script_ordner_pfad"
#read a


echo "########################################################################"
echo "Fertig"
if [ $fehler -gt 0 ]; then
    echo "Bei $fehler Installationsschritten traten Fehler auf"
fi
echo "Wollen Sie das Geraet jetzt neustarten? (y/n)"
echo "########################################################################"

read eingabe
if [ $eingabe = "y" ]; then
    reboot
fi