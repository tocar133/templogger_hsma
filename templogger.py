#!/usr/bin/python3

#####################################################
#   Temperaturlogger mit einem Raspberry Pi Zero    #
#   Bachelorarbeit                                  #
#   Tobias Carstensen, 1920941                      #
#   Wintersemester 2022                             #
#   Hochschule Mannheim                             #
#                                                   #
#   Gehäuse und Platine wurde von                   #
#   Marvin Dürr entwickelt                          #
#                                                   #
#   Aufbauend auf der Bachelorarbeit von            #
#   Marc Grenz                                      #
#####################################################

#import der benötigten Module
import csv
import os
import platform
import sys
import datetime
import time
import dateutil
import subprocess
import numpy as np
import threading
import psutil
import tkinter as tk
from tkinter import Toplevel, messagebox, ttk, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

#import eigener Python Module
import kalibrierung

#import von Modulen für den Raspberry Pi
if platform.system() == "Linux":
    import board
    import digitalio
    import adafruit_max31865


#Klasse für das Messen und Protokollieren der Temperaturdaten
class Templog():
    #Initialisation des Klassenobjekts
    def __init__(self,GUI,Kalibrierung):
        self.GUI = GUI #Variable für den Zugriff auf das GUI Klassen Objekt
        self.Kalibrierung = Kalibrierung
        self.Graph = None #Zugriff auf das Graph Klassen Objekt, Zuweisung des Objekts erfolgt bei Erstellung des Graph Objekts
        self.programm_pfad = str(os.path.realpath(os.path.dirname(__file__)))#Pfad der Programmausführung

        if platform.system() == "Linux":
            #Konfigurieren der Sensorverstärker
            self.spi = board.SPI()
            #self.spi = busio.SPI(board.SCK_1, MOSI=board.MOSI_1, MISO=board.MISO_1) #Verwendet der SPI1 Schnittstelle funktioniert nicht mit diesen Sensorverstärkern
            self.cs1 = digitalio.DigitalInOut(board.D24) #Definieren der Chip Select Signale der Sensorverstärker
            self.cs2 = digitalio.DigitalInOut(board.D23)
            self.cs3 = digitalio.DigitalInOut(board.D22)
            self.cs4 = digitalio.DigitalInOut(board.D21)
            self.sensor1 = adafruit_max31865.MAX31865(self.spi, self.cs1, wires=4) #Definiere den Zugriff auf die Sensorverstärker
            self.sensor2 = adafruit_max31865.MAX31865(self.spi, self.cs2, wires=4) #Verwendet wird der als Default festgelegte PT100 Temperatursensor
            self.sensor3 = adafruit_max31865.MAX31865(self.spi, self.cs3, wires=4) #Verwendet wird der als Default festgelegte Referenzwiderstand von 430Ohm
            self.sensor4 = adafruit_max31865.MAX31865(self.spi, self.cs4, wires=4) #Die Sensoren werden mit einer 4-Leitungsschaltung an die Verstärker angeschlossen

        #Definieren eines Sinussignals für einen DEBUG Betrieb ohne Sensoren
        self.debug_werte1 = np.sin(np.arange(19) / 3) + 124     # Verschiedene Sinus Signale
        self.debug_werte2 = np.sin(np.arange(19) / 3) + 126
        self.debug_werte3 = np.sin(np.arange(19) / 3) * 3 + 8000
        self.debug_werte4 = np.sin(np.arange(19) / 3) * 2 + 125
        self.z1 = 0 #Zähler für die verschiedenen Sinus Signale
        self.z2 = int(len(self.debug_werte2) / 4)
        self.z3 = int(len(self.debug_werte3) / 2)
        self.z4 = int(len(self.debug_werte4) / 4 * 3)

        #Definieren verschiedener Variablen zur Steuerung der veschiedenen Threads
        self.stop_all_threads = threading.Event() #Variable zum beenden aller Threads
        self.stop_all_threads.set()
        self.zeichnen_fertig = threading.Event() #Variable zum verhindern des neu Zeichnens, wenn das alte Zeichnen noch nicht fertig ist
        self.zeichnen_fertig.set()
        self.timer_run = threading.Event() #Variable zum steuern der Pausierung von Darstellung und Protokollierung
        self.timer_run.set()
        self.zeichnen_gestartet = threading.Event() #Variable zum setzten einer Flag fürs Neuzeichnen, wenn das Neuzeichnen zur vorgesehenen Zeit nicht gestartet werden konnte
        self.zeichnen_gestartet.clear()
        self.messung_gestartet = 0 #Variable zum setzten einer Flag wenn eine Messung gestartet wurde

        #Definieren von Variablen zum aufwecken der Threads
        self.zeichnen_warten = threading.Condition() #Aufwecken des Threads zum zeichnen des Diagramms
        self.protokollieren_warten = threading.Condition() #Aufwekcne des Threads zum Protokollieren von Messdaten

        #Definieren der Variablen für die Messdaten des letzten Messzyklus
        self.zeit_stempel = None
        self.temp_sen1 = None
        self.temp_sen2 = None
        self.temp_sen3 = None
        self.temp_sen4 = None

        #Definieren der Listen für die temporäre Speicherung des Messdaten
        self.datumlist = np.array([])
        self.templist1 = np.array([])
        self.templist2 = np.array([])
        self.templist3 = np.array([])
        self.templist4 = np.array([])
        #Definieren der Liste für die Kalibrierungsdaten
        self.kalibrierungs_liste = np.array([])
        self.zeitraum_eintraege = None
        self.darstellungsrate = None
        self.zeichnen_sekunden_counter = None

        #Variablen zum temporären speichern der gewählten Sensornummern bei Differenztemperaturmessung
        self.sen1 = None
        self.sen2 = None

        self.kalibrierfehler = False #Flag zum markieren ob momentan eine kalibrierung geladen ist oder nicht
        self.kalibrierung_laden() #kalibrierung laden

        #Variablen für die verschiedenen Threads
        self.sek_timer = None
        self.running_graph = None
        self.running_protokoll = None
       
    #Thread für einen sekündlichen Timer zur Ausführung der Messung und ggf. Aufwecken der Threads
    #Der Timer startet jeden Durchlauf bei dem Mikrosekundenwert 50000
    def sekunden_timer(self, darstellungsrate, protokollierungsrate):
        #Zähler um die Darstellungs- und Protokollierungszeitpunkte zu ermitteln
        self.zeichnen_sekunden_counter = darstellungsrate
        protokoll_sekunden_counter = protokollierungsrate
        #Zähler für passende Darstellung bei einer Pausierung der Messung
        warten_zeichen_counter = self.zeichnen_sekunden_counter
        #Löschen der Flag das eine Zeichnung gestartet wurde
        self.zeichnen_gestartet.clear()

        #Ermittlung des ersten Durchlaufes des sekunden Timer
        #Wenn die aktuellen Microsekunden über 300000 liegen, dann warte bis die Mikrosekunden wieder bei 50000 sind
        if datetime.datetime.now().microsecond > 300000:
            time.sleep((1050000-datetime.datetime.now().microsecond)/1000000)
        #Starten der Schleife bis der Thread mit der Variable beendet wird
        while not self.stop_all_threads.is_set():
            self.messung() #starten einer neuen Messung
            #Wenn der Timer laufen soll, dann...
            if self.timer_run.is_set():
                self.zeichnen_sekunden_counter += 1 #Erhöhen des Zählers für die Ermittlung eines neuen Zeichenzyklus
                warten_zeichen_counter = self.zeichnen_sekunden_counter #Aktuellen Stand des Zählers für die Pausierung speichern
                #Wenn der Zähler fürs Zeichnen höher oder gleich der Darstellungsrate ist oder
                #die Flag fürs neue Zeichnen gesetzt ist, dann...
                if self.zeichnen_sekunden_counter >= darstellungsrate or self.zeichnen_gestartet.is_set():
                    #Wenn die Flag zum Signalisieren der Fertigstellung des Zeichnens gesetzt ist, dann
                    if self.zeichnen_fertig.is_set():
                        self.zeichnen_fertig.clear() #Lösche die Flag
                        self.zeichnen_sekunden_counter = 0 #Setze den Zähler auf 0
                        with self.zeichnen_warten:
                            self.zeichnen_warten.notify() #Wecke den Thread zum Neuzeichnen auf
                    #Wenn die Flag nicht gesetzt ist und das Zeichnen nicht fertiggestellt ist, dann
                    else:
                        self.zeichnen_gestartet.set() #Setze die Flag, damit das Neuzeichnen sobald möglich gestartet wird
                #Wenn die Protokollierungsrate größer 0 ist, dann...
                if protokollierungsrate > 0:
                    protokoll_sekunden_counter += 1 #Erhöhen des Zählers für die Ermittlung eines neuen Protokollierungszyklus
                    #Wenn der Zähler fürs Protokollieren höher oder gleich der Protokollierungsrate ist, dann...
                    if protokoll_sekunden_counter >= protokollierungsrate:
                        protokoll_sekunden_counter = 0 #Setze den Zähler auf 0
                        with self.protokollieren_warten:
                            self.protokollieren_warten.notify() #Wecke den Thread zum Neuzeichnen auf
            #Wenn der Timer pausiert ist, dann...
            else:
                self.zeichnen_sekunden_counter = darstellungsrate #Setze den Zähler fürs Neuzeichnen auf die Darstellungsrate, damit nach der Pause eine neue Zeichnung beginnt
                warten_zeichen_counter += 1 #Zähler für die passende Darstellung nach einer Pause erhöhen
                #Wenn der Zähler für die passende Darstellung nach einer Pause höher oder gleich der Darstellungsrate ist, dann
                if warten_zeichen_counter >= darstellungsrate:
                    warten_zeichen_counter = 0 #Setze den Zähler auf 0
                    self.datumlist = np.append(self.datumlist, self.zeit_stempel) #Füge der Zeitliste den Zeitstempel der letzten Messung hinzu
                    #Füge den Temperaturlisten einen None Wert hinzu
                    self.templist1 = np.append(self.templist1, None)
                    self.templist2 = np.append(self.templist2, None)
                    self.templist3 = np.append(self.templist3, None)
                    self.templist4 = np.append(self.templist4, None)

                    #Entferne das erste Element in der Zeitliste und in den Temperaturlisten
                    self.datumlist = np.delete(self.datumlist, 0)
                    self.templist1 = np.delete(self.templist1, 0)
                    self.templist2 = np.delete(self.templist2, 0)
                    self.templist3 = np.delete(self.templist3, 0)
                    self.templist4 = np.delete(self.templist4, 0)
            #Warte bis die Microsekunden wieder den Wert 50000 erreicht hat
            time.sleep(1 - ((datetime.datetime.now().microsecond - 50000)/1000000))
    
    #Funktion zum laden der Konfigurationsdatei
    def kalibrierung_laden(self):
        # Versuche aus der kalibrierung.csv Datei die Kalibrierungsdaten auszulesen
        try:
            with open(self.programm_pfad + "/kalibrierung.csv",'r') as datei: #Öffne die Datei kalibrierung.csv zum lesen
                csv_reader = csv.reader(datei, delimiter=';') #lese den Inhalt der .csv Datei, trenne die Inhalte bei jedem ","
                matrix = [row for row in csv_reader] #Weise der Variable die Kalibrierungsdaten zu
        #Wenn die Datei nicht gefunden wurde, dann...
        except FileNotFoundError:
            if platform.system() == "Linux":
                messagebox.showerror(title = "Keine Kalibrierungsdatei",
                    message = "Die Kalibrierungsdatei\n{}/kalibrierung.csv\nwurde nicht gefunden".format(self.programm_pfad)) #Öffne ein Warnungsfenster mit der Warnung das die Kalibrierungsdatei nicht gefunden werden konnte
            self.kalibrierungs_liste = np.array([0,100,0,0,0,0,100,100,100,100])
            self.kalibrierfehler = True #Flag setzten zur Markierung das es ein Fehler beim laden der Kalibrierung gab
            return False #Funktion verlassen und signalisiere das ein Fehler aufgetreten ist
        #Wenn ein Fehler auftrat, dann...
        except:
            if platform.system() == "Linux":
                messagebox.showerror(title = "Fehler beim lesen",
                    message = "Es trat ein Fehler beim lesen der Kalibrierungsdatei auf.".format(self.programm_pfad)) #Öffne ein Warnungsfenster mit der Warnung das beim lesen der Kalibrationsdatei ein Fehler auftrat
            self.kalibrierungs_liste = np.array([0,100,0,0,0,0,100,100,100,100])
            self.kalibrierfehler = True #Flag setzten zur Markierung das es ein Fehler beim laden der Kalibrierung gab
            return False #Funktion verlassen und signalisiere das ein Fehler aufgetreten ist
        
        #Komma durch einen Punkt in den ausgelesenen Werten ersetzen
        matrix_werte = []
        for zeile in matrix:
            matrix_werte.append([])
            for wert in zeile:
                matrix_werte[-1].append(float(wert.replace(",",".")))

        #Kalibirerungsdaten in Variable für den weiteren Gebrauch speichern
        #Kalibrierungswerte                     Ref 0 Grad          Ref 100 Grad
        self.kalibrierungs_liste = np.array([   matrix_werte[0][0], matrix_werte[1][0],
        #                                       Sensor1 0 Grad      Sensor2 0 Grad      Sensor3 0 Grad      Sensor4 0 Grad
                                                matrix_werte[0][1], matrix_werte[0][2], matrix_werte[0][3], matrix_werte[0][4],
        #                                       Sensor1 100 Grad    Sensor2 100 Grad    Sensor3 100 Grad    Sensor4 100 Grad
                                                matrix_werte[1][1], matrix_werte[1][2], matrix_werte[1][3], matrix_werte[1][4]])

        self.kalibrierfehler = False #Flag löschen, Markierung das eine Kalibrierung geladen wurde

    #Funktion zum Vorbereiten der Messungen
    def vorbereitung(self, zeitraum, darstellungsrate, popup_window,differenzmessung,sen1=None,sen2=None):
        popup_window.destroy() #Schließe das Pop Up Fenster für die Eingaben der Mess- und Protokollierungsparameter
        #Wenn momentan eine andere Messung läuft, dann...
        if self.messung_gestartet:
            antwort = messagebox.askyesno(title="Messung beenden?", message="Wollen Sie die aktuelle Messung beenden?") #Öffne ein Fenster und frage ob die aktuelle Messung beendent werden soll
            #Wenn die Messung beendet werden soll, dann beende die Messung, wenn nicht dann verlasse die Funktion
            if antwort:
                self.stop_messung()
            else:
                return False
        #self.GUI.zeitraum_einagbe.delete(0,tk.END)
        #self.GUI.zeitraum_einagbe.insert(0,zeitraum)
        self.GUI.neuer_zeitraum_var.set(zeitraum)
        self.messung_gestartet = 1 #Setze die Variable auf 1 um zu Signalisieren, das eine Messung gestartet wurde
        
        self.kalibrierung_laden() #Kalibrierung laden
        
        #Anzahl der Messpunkte im Graphen ermitteln
        self.zeitraum_eintraege = int(zeitraum * 60 / darstellungsrate)
        self.darstellungsrate = darstellungsrate

        #Listen für die Messung vorbereiten
        akutelle_zeit = datetime.datetime.now() #aktuelle Zeit auslesen
        self.datumlist = np.array([akutelle_zeit - datetime.timedelta(seconds = i * int(darstellungsrate)) for i in range(self.zeitraum_eintraege,0,-1)]) #Zeitpunkte ermitteln für den Graphen
        self.templist1 = np.array([None] * self.zeitraum_eintraege) #Temperaturlisten mit None Werten füllen
        self.templist2 = np.array([None] * self.zeitraum_eintraege)
        self.templist3 = np.array([None] * self.zeitraum_eintraege)
        self.templist4 = np.array([None] * self.zeitraum_eintraege)
        
        #Treeview für den letzte Einträge Log leeren
        for i in self.GUI.treeview_log1.get_children():
            self.GUI.treeview_log1.delete(i)
        #for i in self.GUI.treeview_log2.get_children():
        #    self.GUI.treeview_log2.delete(i)
        #Treeview für die aktuelle Messung vorbereiten
        if differenzmessung:
            self.GUI.treeview_log1.heading('Zeitstempel', text='Zeitstempel') #Spaltenüberschriften des Treeviews setzen
            self.GUI.treeview_log1.heading('Sensor1', text='Sensor {}'.format(sen1))
            self.GUI.treeview_log1.heading('Sensor2', text='Sensor {}'.format(sen2))
            self.GUI.treeview_log1.heading('Sensor3', text='Differenztemperatur')
            
            self.GUI.treeview_log1.column("Sensor3", width=204,stretch=1) #Spaltengröße einstellen
            self.GUI.treeview_log1["displaycolumns"]=("Zeitstempel", "Sensor1", "Sensor2", "Sensor3") #Bestimmen welche Spalten angezeigt werden sollen
        else:
            self.GUI.treeview_log1.heading('Zeitstempel', text='Zeitstempel')
            self.GUI.treeview_log1.heading('Sensor1', text='Sensor 1')
            self.GUI.treeview_log1.heading('Sensor2', text='Sensor 2')
            self.GUI.treeview_log1.heading('Sensor3', text='Sensor 3')
            
            self.GUI.treeview_log1.column("Sensor3", width=102,stretch=1)
            self.GUI.treeview_log1["displaycolumns"]=("Zeitstempel", "Sensor1", "Sensor2", "Sensor3", "Sensor4")

        self.Graph.ma = None #Maximalen Y-Wert der Y-Achse löschen
        self.Graph.mi = None #Minimalen Y-Wert der Y-Achse löschen

        self.z1 = 0 #Zähler für die verschiedenen Sinus Signale zurücksetzen
        self.z2 = int(len(self.debug_werte2) / 4)
        self.z3 = int(len(self.debug_werte3) / 2)
        self.z4 = int(len(self.debug_werte4) / 4 * 3)

        #Variablen zurücksetzen
        self.sen1 = None
        self.sen2 = None

        self.stop_all_threads.clear() #Flag für das beenden aller Threads löschen
        #Funktion verlassen und signalisieren, dass alles erfolgreich war
        return True

    #Funktion zum Vorbereiten und zum starten der benötigten Threads für Echtzeitmessungen
    def live_graph_starten(self, darstellungsrate, zeitraum, dateiname, protokollierungsrate, popup_window):
        #Wenn es bei der Vorbereitung Fehler gab, dann verlasse diese Funktion
        if not self.vorbereitung(zeitraum, darstellungsrate, popup_window,False): return
        #Erstelle den Thread zum Zeichnen des Graphes und starte diesen
        self.running_graph = threading.Thread(target=self.live_graph)
        self.running_graph.start()
        #Wenn protokolliert werden soll, dann...
        if protokollierungsrate > 0:
            #Erstelle den Thread zum protokollieren der Messdaten und starte diesen
            self.running_protokoll = threading.Thread(target=self.protokollieren, args=(dateiname,))
            self.running_protokoll.start()
        #Erstelle den Thread für den Sekunden Timer und starte diesen
        self.sek_timer = threading.Thread(target=self.sekunden_timer, args=(darstellungsrate,protokollierungsrate))
        self.sek_timer.start()

    #Funktion zum Vorbereitung und zum starten der benötigten Threads für eine Echtzeit-Differenzmessung
    def differenz_graph_starten(self, darstellungsrate, zeitraum, dateiname, protokollierungsrate, sen1, sen2, popup_window):
        #Wenn es bei der Vorbereitung Fehler gab, dann verlasse diese Funktion
        if not self.vorbereitung(zeitraum, darstellungsrate,popup_window,True,sen1,sen2): return
        
        #Deaktiviere alle Sensor-Checkboxen, da die Sensoren bereits bei der Parameter Festlegung eingestellt wurden
        self.GUI.sensor1_checkbox.config(state=tk.DISABLED)
        self.GUI.sensor2_checkbox.config(state=tk.DISABLED)
        self.GUI.sensor3_checkbox.config(state=tk.DISABLED)
        self.GUI.sensor4_checkbox.config(state=tk.DISABLED)
    
        #Setze ein Haken in die Checkboxen der Sensoren die ausgewählt wuden, bei den anderen entferne den Haken
        #Ändere die Farbe der Checkboxen der ausgewählten Sensoren, setze eine andere Farbe wenn diese nicht ausgewählt wurden
        if 1 in [sen1,sen2]:
            self.GUI.sensorvar1.set(True)
            self.GUI.sensor1_checkbox.config(disabledforeground="#343434")
        else:
            self.GUI.sensorvar1.set(False)
            self.GUI.sensor1_checkbox.config(disabledforeground="#a3a3a3")
            self.GUI.sensor1_label.config(fg="#a3a3a3")
        if 2 in [sen1,sen2]:
            self.GUI.sensorvar2.set(True)
            self.GUI.sensor2_checkbox.config(disabledforeground="#343434")
        else:
            self.GUI.sensor2_checkbox.config(disabledforeground="#a3a3a3")
            self.GUI.sensorvar2.set(False)
        if 3 in [sen1,sen2]:
            self.GUI.sensorvar3.set(True)
            self.GUI.sensor3_checkbox.config(disabledforeground="#343434")
        else:
            self.GUI.sensor3_checkbox.config(disabledforeground="#a3a3a3")
            self.GUI.sensorvar3.set(False)
            self.GUI.sensor3_label.config(fg="#a3a3a3")
        if 4 in [sen1,sen2]:
            self.GUI.sensorvar4.set(True)
            self.GUI.sensor4_checkbox.config(disabledforeground="#343434")
        else:
            self.GUI.sensorvar4.set(False)
            self.GUI.sensor4_checkbox.config(disabledforeground="#a3a3a3")
            self.GUI.sensor4_label.config(fg="#a3a3a3")

        #Erstelle den Thread zum Zeichnen des Graphes und starte diesen
        self.running_graph = threading.Thread(target=self.differenz_graph, args=(sen1,sen2))
        self.running_graph.start()
        #Wenn protokolliert werden soll, dann...
        if protokollierungsrate > 0:
            #Erstelle den Thread zum protokollieren der Messdaten und starte diesen
            self.running_protokoll = threading.Thread(target=self.protokollieren, args=(dateiname,sen1,sen2))
            self.running_protokoll.start()
        #Erstelle den Thread für den Sekunden Timer und starte diesen
        self.sek_timer = threading.Thread(target=self.sekunden_timer, args=(darstellungsrate,protokollierungsrate))
        self.sek_timer.start()

    #Funktion zur Messung der Messwerte mit dem passenden Zeitstempel
    def messung(self):
        self.zeit_stempel = datetime.datetime.now() #Speichere den aktuelle Zeitstempel
        #Wenn das Programm im Debug Modus ist, dann...
        if DEBUG:
            #Gib als Messdaten den Index der Debug Sinuswerte des zugehörigen Zählers
            self.temp_sen1 = round(self.debug_werte1[self.z1], 3)
            self.z1 = (self.z1 + 1) % len(self.debug_werte1)
            #self.temp_sen1 = round(random.uniform(0,100),3)

            self.temp_sen2 = round(self.debug_werte2[self.z2], 3)
            self.z2 = (self.z2 + 1) % len(self.debug_werte2)
            #self.temp_sen2 = round(random.uniform(0,100),3)
            
            self.temp_sen3 = round(self.debug_werte3[self.z3], 3)
            self.z3 = (self.z3 + 1) % len(self.debug_werte3)
            #self.temp_sen3 = round(random.uniform(0,100),3)

            self.temp_sen4 = round(self.debug_werte4[self.z4], 3)
            self.z4 = (self.z4 + 1) % len(self.debug_werte4)
            #self.temp_sen4 = round(random.uniform(0,100),3)
        #Wenn das Programm nicht im Debug Modus ist, dann...
        else:
            #Verrechne die aktuellen Temperaturwerte mit den Kalibrationsdaten der entsprechenden Sensoren und Speicher diesen Wert in der Variable
            self.temp_sen1 = round(self.sensor1.temperature+((self.kalibrierungs_liste[0]-self.kalibrierungs_liste[2])+((self.kalibrierungs_liste[1]-self.kalibrierungs_liste[6])/self.kalibrierungs_liste[1])*self.sensor1.temperature), 3)
            self.temp_sen2 = round(self.sensor2.temperature+((self.kalibrierungs_liste[0]-self.kalibrierungs_liste[3])+((self.kalibrierungs_liste[1]-self.kalibrierungs_liste[7])/self.kalibrierungs_liste[1])*self.sensor2.temperature), 3)
            self.temp_sen3 = round(self.sensor3.temperature+((self.kalibrierungs_liste[0]-self.kalibrierungs_liste[4])+((self.kalibrierungs_liste[1]-self.kalibrierungs_liste[8])/self.kalibrierungs_liste[1])*self.sensor3.temperature), 3)
            self.temp_sen4 = round(self.sensor4.temperature+((self.kalibrierungs_liste[0]-self.kalibrierungs_liste[5])+((self.kalibrierungs_liste[1]-self.kalibrierungs_liste[9])/self.kalibrierungs_liste[1])*self.sensor4.temperature), 3)
    
    #Funktion für den Protokollierungs Thread
    #Die Messwerte vom letzten Messzyklus mit dem entsprechenden Zeitstempel in die Protokolldatei schreiben
    def protokollieren(self, dateiname, sen1=None, sen2=None):
        header_geschrieben = False #Flag zu Markierung, ob der Header geschrieben wurde
        start = self.zeit_stempel #zwischenspeichern der Protokollstartzeit
        
        #Wenn als Dateiname der Wert <<Erster Zeitstempel>> übergeben wurde, dann...
        if dateiname == "<<Erster Zeitstempel>>":
                dateiname = self.zeit_stempel.strftime("%Y_%m_%d_%H_%M_%S") #Definiere den Dateinamen mit dem Zeitstempel
                dateipfad = self.programm_pfad + "/Saves/" + dateiname +".csv" #Lege den Dateipfad mit dem Dateinamen fest
        #Wenn ein anderer Dateiname festgelegt wurde, dann...
        else:
            dateipfad = self.programm_pfad + "/Saves/" + dateiname +".csv" #Lege den Dateipfad mit dem gegebenen Dateinamen fest

        #Schleife solange bis über die Variable alle Threads beendet werden
        while not self.stop_all_threads.is_set():
            with self.protokollieren_warten:
                self.protokollieren_warten.wait() #Warten bis der Thread aufgeweckt werden soll
            #Wenn der Thread beendet werden soll, dann verlasse die Schleife
            if self.stop_all_threads.is_set(): break
            
            #Bei einer Echtzeitmessung soll der Datensatz aus Zeitstempel und der 4 Temperaturwerte bestehen
            if sen2 == None:
                #datensatz = [self.zeit_stempel.strftime("%Y.%m.%d %H:%M:%S"), self.temp_sen1, self.temp_sen2, self.temp_sen3, self.temp_sen4] #Datensatz bilden
                datensatz = [self.zeit_stempel.strftime("%Y.%m.%d %H:%M:%S"),str(self.temp_sen1).replace(".",","),str(self.temp_sen2).replace(".",","),str(self.temp_sen3).replace(".",","),str(self.temp_sen4).replace(".",",")]
            #Bei einer Differenzmessung soll der Datensatz aus dem Zeitstempel und der Differenztemperatur der gewählten Sensoren bestehen
            else:
                temp1 = [self.temp_sen1,self.temp_sen2,self.temp_sen3,self.temp_sen4][sen1-1] #Temperaturwerte der gewählten Sensoren auswählen
                temp2 = [self.temp_sen1,self.temp_sen2,self.temp_sen3,self.temp_sen4][sen2-1]
                datensatz = [self.zeit_stempel.strftime("%Y.%m.%d %H:%M:%S"), str(round(temp1-temp2,3)).replace(".",",")] #Datensatz bilden
            #Wenn der Header bereits geschrieben ist, prüfe ob es die Protokolldatei noch gibt um zu ermitteln ob der Header in einer neuen Datei erneut geschrieben werden muss
            if header_geschrieben:
                header_geschrieben = os.path.exists(dateipfad) #Prüfen ob die Protokolldatei bereits existiert
            kalibrierung = "" #Text für die Kalibrierung setzen
            #Wenn ein Fehler bei dem laden der Kalibrierung war, dann den Text der Kalibrierung auf unkalibriert setzten
            if self.kalibrierfehler:
                kalibrierung = " (unkalibriert)"
            #Protokolldatei zum erweitern öffnen
            with open(dateipfad, 'a', newline='') as datei:
                schreiber = csv.writer(datei,delimiter=';') #Variable zum schreiben in die Protokolldatei erstellen
                #Wenn die Protokolldatei nicht existiert, dann...
                if not header_geschrieben:
                    #Wenn es eine Echtzeitmessung ist, dann...
                    if sen2 == None:
                        #Schreibe die Beschreibung der Echtzeitmessung in die ersten 2 Zeilen der Protokolldatei
                        schreiber.writerow(["Temperaturlogger{} wurde am {} um {} gestartet.".format(kalibrierung,start.strftime("%d.%m.%Y"),start.strftime("%H:%M:%S"))])
                        schreiber.writerow(["Zeitstempel, Sensor 1, Sensor 2, Sensor 3, Sensor 4"])
                    #Wenn es eine Differenzmessung ist, dann...
                    else:
                        #Schreibe die Beschreibung der Differenzmessung in die ersten 2 Zeilen der Protokolldatei
                        schreiber.writerow(["Differenztemperaturlogger{} wurde am {} um {} gestartet.".format(kalibrierung,start.strftime("%d.%m.%Y"),start.strftime("%H:%M:%S"))])
                        schreiber.writerow(["Zeitstempel, Sensor {} - Sensor {}".format(sen1,sen2)])
                header_geschrieben = True #Flag setzten zur Markierung, dass der Header geschrieben wurde
                #Schreibe den Datensatz in die Protokolldatei
                schreiber.writerow(datensatz)

    #Funktion für den Thread für die Darstellung der Echtzeitdaten im Graphen
    #Schleife zur wiederholten Darstellung der Messdaten im Graph, bis dieser über eine Flag beendet wird
    def live_graph(self):
        #Schleife solange bis der Thread mit der Variable beendet wird
        while not self.stop_all_threads.is_set():
            with self.zeichnen_warten:
                self.zeichnen_warten.wait() #Warte bis der Thread aufgeweckt wird
            #Wenn der Thread beendet werden soll verlasse die Schleife
            if self.stop_all_threads.is_set(): break
            self.zeichnen_gestartet.clear() #Lösche die Flag zum starten eines Darstellungszyklus

            #zeitstempel und Temperaturen temporär zwischenspeichern
            datum = self.zeit_stempel
            temp1 = self.temp_sen1
            temp2 = self.temp_sen2
            temp3 = self.temp_sen3
            temp4 = self.temp_sen4

            #Den Zeitstempel und die Temperaturwerte der letzten Messung in die Listen speichern
            self.datumlist = np.append(self.datumlist, self.zeit_stempel)
            self.templist1 = np.append(self.templist1, self.temp_sen1)
            self.templist2 = np.append(self.templist2, self.temp_sen2)
            self.templist3 = np.append(self.templist3, self.temp_sen3)
            self.templist4 = np.append(self.templist4, self.temp_sen4)

            #Die ältesten Einträge in den Listen löschen
            if len(self.datumlist) > 100000:
                self.datumlist = np.delete(self.datumlist, 0)
                self.templist1 = np.delete(self.templist1, 0)
                self.templist2 = np.delete(self.templist2, 0)
                self.templist3 = np.delete(self.templist3, 0)
                self.templist4 = np.delete(self.templist4, 0)
            
            anzeigen = [self.GUI.sensorvar1.get(), self.GUI.sensorvar2.get(), self.GUI.sensorvar3.get(), self.GUI.sensorvar4.get()] #Ermitteln welche Sensoren im Graph angezeigt werden sollen und dies in einer Liste speichern
            #sta = datetime.datetime.now()
            self.Graph.update(anzeigen,None,None) #Funktion zum update des Graphen aufrufen
            #print("Dauer für Graph update: {}\t\t{}".format((datetime.datetime.now()-sta).total_seconds(),len(self.datumlist)))
            #Wenn der Thread beendet werden soll verlasse die Schleife
            if self.stop_all_threads.is_set():break
            self.GUI.update_sensor_label(anzeigen,temp1,temp2,temp3,temp4) #Temperaturanzeige der Sensoren updaten
            self.GUI.update_treeview(datum,temp1,temp2,temp3,temp4) #Textlog der letzten Darstellungszeitpunkte updaten
            #Flag setzten um zu signalisieren, dass der Graph neu gezeichnet wurde
            self.zeichnen_fertig.set()

    #Funktion für den Thread für die Darstellung der Differenztemperatur im Graphen
    #Schleife zur wiederholten Darstellung der Differenzmessdaten im Graph, bis dieser über eine Flag beendet wird
    def differenz_graph(self, sen1, sen2):
        #Sensoren speichern, welche für die Differenzmessung gewählt wurden
        self.sen1 = sen1
        self.sen2 = sen2
        #Schleife bis der Thread mit der Variable beendet wird
        while not self.stop_all_threads.is_set():
            with self.zeichnen_warten:
                self.zeichnen_warten.wait() #Warten bis der Thread aufgeweckt wird
            #Wenn der Thread beendet werden soll verlasse die Schleife
            if self.stop_all_threads.is_set(): break
            self.zeichnen_gestartet.clear() #Lösche die Flag zum starten eines Darstellungszyklus

            #Temperaturen der gewählten Sensoren ermitteln
            temp1 = [self.temp_sen1,self.temp_sen2,self.temp_sen3,self.temp_sen4][sen1-1]
            temp2 = [self.temp_sen1,self.temp_sen2,self.temp_sen3,self.temp_sen4][sen2-1]
            #zeitstempel und Temperaturen temporär zwischenspeichern
            datum = self.zeit_stempel
            t1 = self.temp_sen1
            t2 = self.temp_sen2
            t3 = self.temp_sen3
            t4 = self.temp_sen4
            #Zeitstempel und die Differenztemperatur in die Listen speichern
            self.datumlist = np.append(self.datumlist, self.zeit_stempel)
            self.templist1 = np.append(self.templist1, round(temp1-temp2,3))
            #Ältesten Wert in der Liste löschen
            self.datumlist = np.delete(self.datumlist, 0)
            self.templist1 = np.delete(self.templist1, 0)
            
            anzeigen = [self.GUI.sensorvar1.get(), self.GUI.sensorvar2.get(), self.GUI.sensorvar3.get(), self.GUI.sensorvar4.get()] #Ermitteln welche Temperaturlabel der Sensoren aktuallisiert werden sollen
            self.Graph.update([1,0,0,0],sen1,sen2) #Funktion zum update des Graphen aufrufen
            #Wenn der Thread beendet werden soll verlasse die Schleife
            if self.stop_all_threads.is_set():return
            self.GUI.update_sensor_label(anzeigen,t1,t2,t3,t4) #Temperaturanzeige der Sensoren updaten
            self.GUI.update_treeview(datum,temp1,temp2) #Textlog der letzten Darstellungszeitpunkte updaten
            #Flag setzten um zu signalisieren, dass der Graph neu gezeichnet wurde
            self.zeichnen_fertig.set()
    
    #Funktion zum beenden der Threads
    def threads_stop(self,timer_thread,protokoll_thread,graph_thread):
        #Wenn eine Messung gestartet wurde, dann beende die gestarteten Threads
        if self.messung_gestartet:
            #Wenn die Variable ein Thread ist, dann...
            if timer_thread != None:
                timer_thread.join() #Warte bis der Thread beendet ist
            
            #Wenn die Variable ein Thread ist, dann...
            if protokoll_thread != None:
                #Schleife bis der Thread beendet wurde
                while True:
                    #Wenn der Thread noch läuft, dann...
                    if protokoll_thread.is_alive():
                        #Thread aufwecken
                        with self.protokollieren_warten:
                            self.protokollieren_warten.notify()
                        #Warten bis Thread beendet wurde, max Wartezeit 0,5 Sek
                        protokoll_thread.join(0.5)
                    #Wenn der Thread nicht läuft, dann Schleife verlassen
                    else: break
                    
            #Wenn eine Messung gestartet wurde, dann beende die gestarteten Threads
            if graph_thread != None:
                #Schleife bis der Thread beendet wurde
                while True:
                    #Wenn der Thread noch läuft, dann...
                    if graph_thread.is_alive():
                        #Thread aufwecken
                        with self.zeichnen_warten:
                            self.zeichnen_warten.notify()
                        #Warten bis Thread beendet wurde, max Wartezeit 0,5 Sek
                        graph_thread.join(0.5)
                    #Wenn der Thread nicht läuft, dann Schleife verlassen
                    else: break

            #Stop der Messung mit dem aktuellen Zeitstempel in der Konsole bekannt geben
            print(datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S") + " Messung gestoppt")
            #Flag löschen, dass keine Messung gestartet ist
            self.messung_gestartet = 0

    #Funktion zum zurücksetzten der Bedienoberfläche und zum beenden der Messung
    def stop_messung(self):
        #Checkboxen der Sensoren wieder bedienbar machen
        #Textfarbe der Temperaturanzeige der Sensoren wieder auf schwarz setzen
        if self.GUI.sensor1_label.cget("text") != "nicht verfügbar":
            self.GUI.sensor1_checkbox.config(state=tk.NORMAL)
            self.GUI.sensor1_label.config(fg="black")
        if self.GUI.sensor2_label.cget("text") != "nicht verfügbar":
            self.GUI.sensor2_checkbox.config(state=tk.NORMAL)
            self.GUI.sensor2_label.config(fg="black")
        if self.GUI.sensor3_label.cget("text") != "nicht verfügbar":
            self.GUI.sensor3_checkbox.config(state=tk.NORMAL)
            self.GUI.sensor3_label.config(fg="black")
        if self.GUI.sensor4_label.cget("text") != "nicht verfügbar":
            self.GUI.sensor4_checkbox.config(state=tk.NORMAL)
            self.GUI.sensor4_label.config(fg="black")

        self.stop_all_threads.set() #Variable setzen zum beenden der Threads

        #Flags auf Ausgangspunkt setzen
        self.zeichnen_gestartet.clear()
        self.zeichnen_fertig.set()
        self.timer_run.set()

        thr = threading.Thread(target=self.threads_stop,args=(self.sek_timer,self.running_protokoll,self.running_graph))
        thr.start()

        time.sleep(1)
        
        #Menüeintrag auf Ausgangpunkt zurücksetzen
        self.GUI.options.entryconfigure(2,label="Messung pausieren")

#Klasse zum darstellen und steuern der Bedienoberfläche
class GUI():
    #Initialisation des Klassenobjekts
    def __init__(self):
        self.min_darstellungsrate = 4
        self.sensorliste = [1,2,3,4] #Liste für die Auswahl der möglichen Sensoren
        self.text_log = [] #Definieren der Liste für den Textlog der letzten Darstellungseinträge
        self.aktuallisierung_beendet = threading.Event()
        self.aktuallisierung_beendet.set()
        #Erstellen des Programmfensters
        self.root = tk.Tk()
        self.root.title("Templogger") #Programmtitel festlegen
        #self.root.attributes('-type')
        self.root.geometry("{}x{}".format(self.root.winfo_screenwidth(), self.root.winfo_screenheight()))
        self.root.configure(bg="white") #Hintergrundfarbe des Fensters festlegen
        self.root.minsize(width=880,height=350)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview.Heading', font=("sans-serif",10))

        self.Kalibrierung = kalibrierung.Kalibrierung(self)
        self.Templogger = Templog(self,self.Kalibrierung) #Klassenobjekt zur Temperaturmessung erstellen
        self.Kalibrierung.Templogger = self.Templogger

        #Menüleiste und Untermenüs erstellen
        self.menubar = tk.Menu(self.root, background='#22376F', foreground='white', activebackground='white', activeforeground='black') #Menüleiste erstellen
        
        self.liveGraphsMenu = tk.Menu(self.menubar, tearoff=0) #Menüpunkt zum starten einer Echtzeittemperaturmessung erstellen
        self.liveGraphsMenu.add_command(label="Messungen starten ohne Daten zu protokollieren", command=self.live_graph_popup) #Untermenüpunt Echtzeitmessung ohne Protokoll
        self.liveGraphsMenu.add_command(label="Messungen starten, Daten protokollieren ohne einstellbare Abtastrate für die Darstellung", command=self.live_graph_protokoll_static_popup) #Untermenüpunt Echtzeitmessung mit Protokoll bei gleicher Darstellungs- und Protokollrate
        self.liveGraphsMenu.add_command(label="Messungen starten, Daten protokollieren mit einstellbarer Abtastrate für die Darstellung", command=self.live_graph_protokoll_popup) #Untermenüpunt Echtzeitmessung mit Protokoll
        
        self.differenzGraphsMenu = tk.Menu(self.menubar, tearoff=0)#Menüpunkt zum starten einer Differenztemperaturmessung erstellen
        self.differenzGraphsMenu.add_command(label="Messungen für einen Differenzengrafen starten ohne Daten zu protokollieren", command=self.differenz_graph_popup) #Untermenüpunt Differenzmessung ohne Protokoll
        self.differenzGraphsMenu.add_command(label="Messungen für einen Differenzengrafen starten, Daten protokollieren ohne einstellbare Abtastrate für die Darstellung", command=self.differenz_graph_protokoll_static_popup)#Untermenüpunt Differenzmessung mit Protokoll bei gleicher Darstellungs- und Protokollrate
        self.differenzGraphsMenu.add_command(label="Messungen für einen Differenzengrafen starten, Daten protokollieren mit einstellbarer Abtastrate für die Darstellung", command=self.differenz_graph_protokoll_popup) #Untermenüpunt Differenzmessung mit Protokoll
        
        self.loadGraphs = tk.Menu(self.menubar, tearoff=0)#Menüpunkt zum laden protokollierter Daten erstellen
        self.loadGraphs.add_command(label="Lade existierende Datei und bilde die Daten Grafisch ab", command=self.protokoll_daten_popup) #Untermenüpunkt zum laden eines Protokolls einer Echtzeitmessung
        self.loadGraphs.add_command(label="Lade existierende Datei und bilde einen Differenzgrafen ab", command=self.Protokolldaten_differenz_popup) #Untermenüpunkt zum laden eines Protokolls und der Bildung einer Differenztemperatur
        self.loadGraphs.add_command(label="Speicherort öffnen", command=self.open_save_folder) #Untermenüpunkt zum öffnen des Speicherorts

        self.options = tk.Menu(self.menubar, tearoff=0)#Menüpunkt für weitere Bedienpunkte
        self.options.add_command(label='Pt100 Temperatursensoren kalibrieren', command= self.Kalibrierung.start_kalibrieren) #Untermenüpunkt zum starten der Sensorkalibrierung
        self.options.add_separator() #Trennstrich zwischen den Untermenüpunkten
        self.options.add_command(label="Messungen pausieren", command=self.messung_pausieren) #Untermenüpunkt zum pausieren der Messung bzw. zum fortsetzen einer pausierten Messung
        self.options.add_command(label="Messungen stoppen", command=self.Templogger.stop_messung) #Untermenüpunkt zum stoppen der akutellen Messung
        self.options.add_command(label="Messungen stoppen und neu starten", command=self.restart) #Untermenüpunkt zum stoppen der aktuellen Messung und zum neustarten des Programms
        self.options.add_command(label="Beenden", command=self.close) #Untermenüpunkt zum beenden des Programms

        #Menüpunkte zur Menüleiste hinzufügen und den Name der Menüpunkte festlegen
        self.menubar.add_cascade(label='Echtzeitgraf', menu=self.liveGraphsMenu)
        self.menubar.add_cascade(label='Differenzengrafen', menu=self.differenzGraphsMenu)
        self.menubar.add_cascade(label='Existierende Dateien laden', menu=self.loadGraphs)
        self.menubar.add_cascade(label='Weitere Optionen', menu=self.options)

        if platform.system() != "Linux":
            self.liveGraphsMenu.entryconfig(0, state="disabled")
            self.liveGraphsMenu.entryconfig(1, state="disabled")
            self.liveGraphsMenu.entryconfig(2, state="disabled")
            self.differenzGraphsMenu.entryconfig(0, state="disabled")
            self.differenzGraphsMenu.entryconfig(1, state="disabled")
            self.differenzGraphsMenu.entryconfig(2, state="disabled")
            self.options.entryconfig(0, state="disabled")
            self.options.entryconfig(2, state="disabled")
            self.options.entryconfig(3, state="disabled")
            self.options.entryconfig(4, state="disabled")

        self.root.config(menu=self.menubar) #Menüleiste zum Fenster hinzufügen

        #Definieren und den Standartwert der Variable setzen für den aktuellen Status der Sensorcheckboxen
        self.sensorvar1 = tk.BooleanVar()
        self.sensorvar1.set(True)
        self.sensorvar2 = tk.BooleanVar()
        self.sensorvar2.set(True)
        self.sensorvar3 = tk.BooleanVar()
        self.sensorvar3.set(False)
        self.sensorvar4 = tk.BooleanVar()
        self.sensorvar4.set(False)

        #Erstellen der Sensorcheckboxen und der Sensortemperaturanzeige
        self.sensor_leiste_frame = tk.Frame(self.root,bg="lightgrey")
        self.sensor_leiste_frame.pack(fill="x")
        self.sensor_frame = tk.Frame(self.sensor_leiste_frame,bg="lightgrey") #Platzieren der Elemente in einem Frame
        self.sensor_frame.pack()
        #Sensorcheckboxen erstellen und platzieren
        self.sensor1_checkbox = tk.Checkbutton(self.sensor_frame,width=18,borderwidth=0,highlightthickness=0,bg="lightgrey", text='Sensor 1', variable=self.sensorvar1, onvalue=1, offvalue=0,command=self.graph_aktuallisieren)
        self.sensor2_checkbox = tk.Checkbutton(self.sensor_frame,width=18,borderwidth=0,highlightthickness=0,bg="lightgrey", text='Sensor 2', variable=self.sensorvar2, onvalue=1, offvalue=0,command=self.graph_aktuallisieren)
        self.sensor3_checkbox = tk.Checkbutton(self.sensor_frame,width=18,borderwidth=0,highlightthickness=0,bg="lightgrey", text='Sensor 3', variable=self.sensorvar3, onvalue=1, offvalue=0,command=self.graph_aktuallisieren)
        self.sensor4_checkbox = tk.Checkbutton(self.sensor_frame,width=18,borderwidth=0,highlightthickness=0,bg="lightgrey", text='Sensor 4', variable=self.sensorvar4, onvalue=1, offvalue=0,command=self.graph_aktuallisieren)
        self.sensor1_checkbox.grid(row=0, column=0)
        self.sensor2_checkbox.grid(row=0, column=1)
        self.sensor3_checkbox.grid(row=0, column=2)
        self.sensor4_checkbox.grid(row=0, column=3)
        #Sensortemperaturanzeige erstellen und platzieren
        self.sensor1_label = tk.Label(self.sensor_frame,bg="lightgrey",borderwidth=0,highlightthickness=0, text="nicht ausgewählt")
        self.sensor2_label = tk.Label(self.sensor_frame,bg="lightgrey",borderwidth=0,highlightthickness=0, text="nicht ausgewählt")
        self.sensor3_label = tk.Label(self.sensor_frame,bg="lightgrey",borderwidth=0,highlightthickness=0, text="nicht ausgewählt")
        self.sensor4_label = tk.Label(self.sensor_frame,bg="lightgrey",borderwidth=0,highlightthickness=0, text="nicht ausgewählt")
        self.sensor1_label.grid(row=1, column=0)
        self.sensor2_label.grid(row=1, column=1)
        self.sensor3_label.grid(row=1, column=2)
        self.sensor4_label.grid(row=1, column=3)

        self.sensoren_pruefen = tk.Button(self.sensor_frame,text="Sensoren prüfen",command=self.check_sensoren)
        self.sensoren_pruefen.grid(row=0, column=4)

        if platform.system() != "Linux":
            sensorvar = [self.sensorvar1,self.sensorvar2,self.sensorvar3,self.sensorvar4]
            sensorlabel = [self.sensor1_label,self.sensor2_label,self.sensor3_label,self.sensor4_label]
            #Schleife um auf die Sensor Checkboxen zuzugreifen
            for c,checkbox in enumerate([self.sensor1_checkbox,self.sensor2_checkbox,self.sensor3_checkbox,self.sensor4_checkbox]):
                    checkbox.config(state=tk.DISABLED) #Setze die Checkbox zum gesperrten Zustand
                    checkbox.config(disabledforeground="#a3a3a3") #Ändere die Schriftfarbe einer gesperrten Checkbox
                    sensorvar[c].set(False) #Setzte die Variable der Checkbox auf False (nicht gecheckt)
                    sensorlabel[c].config(text="nicht verfügbar") #Setze den Text des Labels der Checkbox
                    #Setze die Schriftfarbe des Labels der Checkbox
                    sensorlabel[c].config(fg="#a3a3a3")
            self.sensoren_pruefen.config(state=tk.DISABLED)
        else:
            self.check_sensoren()
        
        #Erstellen und platzieren des Diagrammelements
        self.Graphmonitor = Graph(self.root, self.Templogger, self)
        self.Graphmonitor.pack(fill="both",expand=True)
 
        self.neuer_zeitraum_var = tk.StringVar() #Variable für die Spinbox zum auswählen der Darstellungsrate

        self.zeitraum_leiste_frame = tk.Frame(self.root,bg="lightgrey")
        self.zeitraum_leiste_frame.pack(fill="x")

        self.zeitraum_leiste_frame.columnconfigure(0, weight=1,uniform="a")
        self.zeitraum_leiste_frame.columnconfigure(1, weight=1)
        self.zeitraum_leiste_frame.columnconfigure(2, weight=1,uniform="a")

        self.neuer_zeitraum_frame = tk.Frame(self.zeitraum_leiste_frame)
        self.neuer_zeitraum_frame.grid(row=0,column=1)

        self.zeitraum_label = tk.Label(self.neuer_zeitraum_frame,text="neuer Zeitraum:")
        self.zeitraum_label.pack(side=tk.LEFT)
        self.zeitraum_eingabe = tk.Spinbox(self.neuer_zeitraum_frame,bg="white",width=6,from_=1,to=9999999999999999999999,textvariable=self.neuer_zeitraum_var)
        self.zeitraum_eingabe.pack(side=tk.LEFT)
        self.minuten_label = tk.Label(self.neuer_zeitraum_frame,text="Minuten")
        self.minuten_label.pack(side=tk.LEFT)
        self.aktuallisieren_button = tk.Button(self.neuer_zeitraum_frame,text="Aktuallisieren",command= lambda: self.neuer_zeitraum(self.neuer_zeitraum_var.get()))
        self.aktuallisieren_button.pack(side=tk.LEFT)

        self.toolitems = NavigationToolbar2Tk.toolitems
        NavigationToolbar2Tk.toolitems = []
        toolbar = NavigationToolbar2Tk(self.Graphmonitor.canvas, self.zeitraum_leiste_frame, pack_toolbar=False)
        toolbar.config(background="lightgrey")
        toolbar.update()
        toolbar.grid(row=0,column=2,sticky="E")
        NavigationToolbar2Tk.toolitems = self.toolitems
        
        #Erstellen und platzieren der Textboxen für die Einträge der letzten Darstellungspunkte
        self.treeview_columns = ["Zeitstempel","Sensor1","Sensor2","Sensor3","Sensor4"]
        self.treeview_log1 = ttk.Treeview(self.root,columns=self.treeview_columns,show="headings",height=5)
        self.treeview_log1.pack()

        self.treeview_log1.heading('Zeitstempel', text='Zeitstempel')
        self.treeview_log1.heading('Sensor1', text='Sensor 1')
        self.treeview_log1.heading('Sensor2', text='Sensor 2')
        self.treeview_log1.heading('Sensor3', text='Sensor 3')
        self.treeview_log1.heading('Sensor4', text='Sensor 4')
        for item in self.treeview_columns:
            self.treeview_log1.column(item, width=102,stretch=1)

        def handle_click(event):
            if self.treeview_log1.identify_region(event.x, event.y) == "separator":
               return "break"
        self.treeview_log1.bind('<Button-1>', handle_click)

        self.root.protocol("WM_DELETE_WINDOW", self.close) #Wenn das Fenster geschlossen wird soll die Funktion close aufgerufen werden
        #Fenster erstellen und darstellen
        self.root.mainloop()

    #Funktion zum Öffnen des Speicherorts der Protokolle
    def open_save_folder(self):
        os.system('xdg-open {}/Saves/'.format(self.Templogger.programm_pfad))

    #Funktion zum öffnen der Bildschirmtastatur
    def open_keyboard(self):
        #Durchlaufe alle vorhandenen Prozesse
        for proc in psutil.process_iter():
            try:
                #Wenn der aktuelle Prozess die matchbox-keyboard gehört, dann beende diesen Prozess
                if "matchbox-keyboa".lower() in proc.name().lower():
                    subprocess.Popen.kill(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        #Starte einen neuen Prozess des matchbox-keyboards
        subprocess.Popen(['matchbox-keyboard'])

    #Funktion zum aktuallisieren des Graphen
    def graph_aktuallisieren(self):
        self.aktuallisierung_beendet.wait()
        self.aktuallisierung_beendet.clear()
        #Wenn keine Messung läuft, nichts machen
        if not self.Templogger.messung_gestartet:
            self.aktuallisierung_beendet.set()
            return
        #Wenn der nächste Darstellungszyklus in den nächsten 3 Sek ist und der Sekunden Timer nicht pausiert ist, dann nichts machen
        if (self.Templogger.zeichnen_sekunden_counter >= self.Templogger.darstellungsrate - 3) and self.Templogger.timer_run.is_set():
            self.aktuallisierung_beendet.set()
            return
        #Funktion aufrufen um den Graphen zu aktuallisieren
        thr = threading.Thread(target=self.Graphmonitor.update,args=([self.sensorvar1.get(), self.sensorvar2.get(), self.sensorvar3.get(), self.sensorvar4.get()],self.Templogger.sen1,self.Templogger.sen2))
        thr.start()
        #self.Graphmonitor.update([self.sensorvar1.get(), self.sensorvar2.get(), self.sensorvar3.get(), self.sensorvar4.get()],self.Templogger.sen1,self.Templogger.sen2)
        self.aktuallisierung_beendet.set()

    #Funktion zum prüfen, welche Sensoren verfügbar sind
    def check_sensoren(self):
        #Wenn eine Messung läuft, dann warte 1 sek um aktuelle Temperaturen zu bekommen
        if self.Templogger.messung_gestartet:
            time.sleep(1)
        #Wenn keine Messung läuft, dann führe eine Temperaturabfrage durch
        else:
            self.Templogger.messung()

        self.sensorliste = [] #Leere die Liste der verfügbaren Sensoren
        #Erstelle Listen um auf die zusammengehörigen elemente zuzugreifen
        sensoren = [self.Templogger.temp_sen1,self.Templogger.temp_sen2,self.Templogger.temp_sen3,self.Templogger.temp_sen4]
        sensorvar = [self.sensorvar1,self.sensorvar2,self.sensorvar3,self.sensorvar4]
        sensorlabel = [self.sensor1_label,self.sensor2_label,self.sensor3_label,self.sensor4_label]
        #Schleife um auf die Sensor Checkboxen zuzugreifen
        for c,checkbox in enumerate([self.sensor1_checkbox,self.sensor2_checkbox,self.sensor3_checkbox,self.sensor4_checkbox]):
            #Wenn die Temperatur des Sensors innerhalb des Bereichs -200 bis +200 Grad liegt, dann...
            if -200 < sensoren[c] < 200:
                self.sensorliste.append(c+1) #Füge die Nummer des Sensors der Sensorlise hinzu
                #Wenn keine Differenzmessung läuft, dann...
                if self.Templogger.sen1 == None:
                    #Wenn die Checkbox nicht den normal Zustand hat, dann...
                    if checkbox.cget("state") != tk.NORMAL:
                        checkbox.config(state=tk.NORMAL) #Setze die Checkbox zum normalen Zustand
                        sensorvar[c].set(False) #Setzte die Variable der Checkbox auf False (nicht gecheckt)
                        sensorlabel[c].config(text="nicht ausgewählt") #Setze den Text des Labels der Checkbox
                        sensorlabel[c].config(fg="black") #Setze die Schriftfarbe des Labels der Checkbox
            #Wenn die Temperatur außerhalb des Bereichs liegt, dann...
            else:
                checkbox.config(state=tk.DISABLED) #Setze die Checkbox zum gesperrten Zustand
                checkbox.config(disabledforeground="#a3a3a3") #Ändere die Schriftfarbe einer gesperrten Checkbox
                sensorvar[c].set(False) #Setzte die Variable der Checkbox auf False (nicht gecheckt)
                sensorlabel[c].config(text="nicht verfügbar") #Setze den Text des Labels der Checkbox
                #Setze die Schriftfarbe des Labels der Checkbox
                sensorlabel[c].config(fg="#a3a3a3")

    #Funktion zum ändern des darzustellenden Zeitraums
    def neuer_zeitraum(self,zeitraum):
        #Wenn keine Messung läuft, nichts machen
        if not self.Templogger.messung_gestartet:
            return
        #Versuche den eingegebenen Zeitraum zu einer Zahl zu konvertieren
        try:
            zeitraum = int(zeitraum)
        #Wenn es nicht geklappt hat, eine Fehlermeldung öffnen und Funktion verlassen
        except:
            messagebox.showerror(title = "Keine gültiger Darstellungszeitraum", message = "Bitte geben Sie für den Darstellungszeitraum eine ganze Zahl ein.")
            return
        #Wenn der Zeitraum kleiner oder gleich 0 ist, dann öffne eine Fehlermeldung und verlasse die Funktion
        if zeitraum <= 0:
            messagebox.showerror(title = "Keine gültiger Darstellungszeitraum", message = "Bitte geben Sie für den Darstellungszeitraum eine Zahl größer 0 ein.")
            return
        
        self.Templogger.zeitraum_eintraege = int(zeitraum * 60 / self.Templogger.darstellungsrate) #Ermittel die Werteanzahl für den neuen Darstellungszeitraum
        #Wenn der neue Zeitraum größer ist als der alte Zeitraum, dann erweitere die Datenlisten mit None Werten damit im Graphen der ausgewählte Zeitraum dargestellt wird
        if len(self.Templogger.datumlist) < self.Templogger.zeitraum_eintraege:
            #Schleife zum Datenlisten auffüllen
            for i in range(self.Templogger.zeitraum_eintraege - len(self.Templogger.datumlist)):
                self.Templogger.datumlist = np.insert(self.Templogger.datumlist,0,self.Templogger.datumlist[0]-datetime.timedelta(seconds=self.Templogger.darstellungsrate)) #Zeitstempel der Einträge erstellen
                #None Werte in die Listen einfügen
                self.Templogger.templist1 = np.insert(self.Templogger.templist1,0,None)
                self.Templogger.templist2 = np.insert(self.Templogger.templist2,0,None)
                self.Templogger.templist3 = np.insert(self.Templogger.templist3,0,None)
                self.Templogger.templist4 = np.insert(self.Templogger.templist4,0,None)
        #Graph aktuallisieren
        self.graph_aktuallisieren()

    #Funktion zur pausieren oder fortsetzen einer Messung
    def messung_pausieren(self):
        #Wenn keine Messung läuft, dann kehre zurück
        if not self.Templogger.messung_gestartet: return
        #Wenn eine Messung läuft, dann...
        if self.Templogger.timer_run.is_set():
            self.options.entryconfigure(2,label="Messung fortsetzen") #Ändere den Text des Menüeintrags
            self.Templogger.timer_run.clear() #Lösche die Flag um die Messung zu pausieren
            print("{} Messung pausiert".format(datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S")))
        #Wenn eine Messung pausiert ist, dann...
        else:
            self.options.entryconfigure(2,label="Messung pausieren") #Ändere den Text des Menüeintrags
            #Setze die Flag zum fortsetzen der Messung
            self.Templogger.timer_run.set()
            print("{} Messung fortgesetzt".format(datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S")))

    #Funktion wechseln des Objekts beim drücken der Tabulatortaste
    def next_element(self,event):
        event.widget.tk_focusNext().focus() #Fokusiere das nächste Element
        #Versuche von dem neu Fokusierten Element den Text auszuwählen
        try:
            event.widget.master.focus_get().tag_add(tk.SEL, "1.0", "end-1c")
        except:None
        #Return break zum durchführen der Aktionen
        return "break"

    #Funktion zum aktuallisieren der Sensortemperaturanzeige
    def update_sensor_label(self,anzeigen,temp1,temp2,temp3,temp4):
        #Wenn über die Liste der Sensor ausgewählt wurde, dann...
        if anzeigen[0]:
            self.sensor1_label.configure(text=str(round(temp1, 2)) + "°C") #Ändere den Text zum Temperaturwert der letzten Messung
        #Sonst...
        elif self.sensor1_label.cget("text") != "nicht verfügbar":
            self.sensor1_label.configure(text="nicht ausgewählt") #Ändere den Text

        if anzeigen[1]:
            self.sensor2_label.configure(text=str(round(temp2, 2)) + "°C")
        elif self.sensor2_label.cget("text") != "nicht verfügbar":
            self.sensor2_label.configure(text="nicht ausgewählt")

        if anzeigen[2]:
            self.sensor3_label.configure(text=str(round(temp3, 2)) + "°C")
        elif self.sensor3_label.cget("text") != "nicht verfügbar":
            self.sensor3_label.configure(text="nicht ausgewählt")

        if anzeigen[3]:
            self.sensor4_label.configure(text=str(round(temp4, 2)) + "°C")
        elif self.sensor4_label.cget("text") != "nicht verfügbar":
            self.sensor4_label.configure(text="nicht ausgewählt")

    #Funktion zum aktuallisieren der Treeviews mit den Einträgen der letzten Darstellungspunkte
    def update_treeview(self,datum,temp1,temp2,temp3=None,temp4=None):
        if temp4 != None:
            #Ermittle die Abstände der Temperaturzahlen für eine gleichmäßige Darstellung in der Textbox
            leerzeichen1 = " "*(9-len(str(temp1)))
            leerzeichen2 = " "*(9-len(str(temp2)))
            leerzeichen3 = " "*(9-len(str(temp3)))
            leerzeichen4 = " "*(9-len(str(temp4)))
            
            daten_string = "{}:{}{},{}{},{}{},{}{}".format(datum.strftime("%H:%M:%S"),leerzeichen1,temp1,leerzeichen2,temp2,leerzeichen3,temp3,leerzeichen4,temp4) #Erstelle den Datentex für die Textbox
        
            self.treeview_log1.insert("", 0, values=[datum.strftime("%H:%M:%S"),temp1,temp2,temp3,temp4]) #Daten in den Treeview einfügen
        else:
            #Ermittle die Abstände der Temperaturzahlen für eine gleichmäßige Darstellung in der Textbox
            leerzeichen1 = " "*(9-len(str(temp1)))
            leerzeichen2 = " "*(9-len(str(temp2)))
            
            daten_string = "{}:{}{} - {}{}= {}".format(datum.strftime("%H:%M:%S"),leerzeichen1,temp1,temp2,leerzeichen2,round(temp1-temp2,3)) #Erstelle den Datentex für die Textbox

            self.treeview_log1.insert("", 0, values=[datum.strftime("%H:%M:%S"),temp1,temp2,round(temp1-temp2,3)]) #Daten in den Treeview einfügen
        #Wenn es 6 Einträge im Treeview sind, dann lösche den letzten Eintrag
        if len(self.treeview_log1.get_children()) == 6:
            self.treeview_log1.delete(self.treeview_log1.get_children()[-1])
        #Gebe den Datentext in der Konsole aus
        print(daten_string)

    #Funktion zum prüfen der Eingabeparameter für eine Echtzeittemperaturmessung
    def live_graph_eingabe_testen(self, darstellungsrate, zeitraum, dateiname,protokollierung, protokollierungsrate, popup_window):
        #Prüfe ob die Darstellungsrate eine Zahl ist
        try:
           darstellungsrate = int(darstellungsrate)
        #Wenn nicht, dann gebe eine Fehlermeldung und verlasse die Funktion
        except:
            messagebox.showerror(title = "Keine ganze Zahl", message = "Bitte geben Sie für die Abtastrate eine ganze Zahl ein.")
            return
        #Prüfe on der Zeitraum eine Zahl ist
        try:
            zeitraum = int(zeitraum)
        #Wenn nicht, dann gebe eine Fehlermeldung und verlasse die Funktion
        except:
            messagebox.showerror(title = "Keine ganze Zahl", message = "Bitte geben Sie für den Zeitraum eine ganze Zahl ein.")
            return
        #Wenn die Protokollierung gestartet werden soll, dann...
        if protokollierung:
            #Prüfe ob die Protokollierungsrate eine Zahl ist
            try:
                protokollierungsrate = int(protokollierungsrate)
            #Wenn nicht, dann gebe eine Fehlermeldung und verlasse die Funktion
            except:
                messagebox.showerror(title = "Keine ganze Zahl", message = "Bitte geben Sie für die Protokollierungsrate eine ganze Zahl ein.")
                return
        #Wenn die Darstellungsrate zu klein ist, dann gebe eine Fehlermeldung und verlasse die Funktion
        if darstellungsrate < self.min_darstellungsrate:
            messagebox.showerror(title = "Zu hohe Darstellungsrate", message = "Bitte geben Sie eine größere Zeit für die Darstellungsrate ein.")
            return
        #Wenn die Darstellungsrate größer als der Zeitraum ist, dann gebe eine Fehlermeldung und verlasse die Funktion
        if darstellungsrate > zeitraum * 60:
            messagebox.showerror(title = "Zu kleiner Zeitraum", message = "Bitte geben Sie eine Zeitraum der größer als die Darstellungsrate ist ein.")
            return
        #Wenn alle Prüfung erfolgreich waren, dann gebe die Parameter weiter um die Messung zu starten
        self.Templogger.live_graph_starten(int(darstellungsrate), int(zeitraum), dateiname, int(protokollierungsrate), popup_window)

    #Funktion zum prüfen der Eingabeparameter für eine Differenztemperaturmessung
    def differenz_graph_eingabe_testen(self,darstellungsrate,zeitraum,dateiname,protokollierung,protokollierungsrate,sen1,sen2,popup_window):
        #Prüfe ob die Darstellungsrate eine Zahl ist
        try:
           darstellungsrate = int(darstellungsrate)
        #Wenn nicht, dann gebe eine Fehlermeldung und verlasse die Funktion
        except:
            messagebox.showerror(title = "Keine ganze Zahl", message = "Bitte geben Sie für die Abtastrate eine ganze Zahl ein.")
            return
        #Prüfe on der Zeitraum eine Zahl ist
        try:
            zeitraum = int(zeitraum)
        #Wenn nicht, dann gebe eine Fehlermeldung und verlasse die Funktion
        except:
            messagebox.showerror(title = "Keine ganze Zahl", message = "Bitte geben Sie für den Zeitraum eine ganze Zahl ein.")
            return
        #Wenn die Protokollierung gestartet werden soll, dann...
        if protokollierung:
            #Prüfe ob die Protokollierungsrate eine Zahl ist
            try:
                protokollierungsrate = int(protokollierungsrate)
                if protokollierungsrate < 1: raise("Protokollierungsrate kleiner 1 Sekunde")
            except:
                messagebox.showerror(title = "Keine ganze Zahl", message = "Bitte geben Sie für die Protokollierungsrate eine ganze Zahl größer 0 ein.")
                return
        #Prüfe ob die Eingegebene Sensornummer eine gültige Sensornummer ist
        try:
            sen1 = int(sen1)
            if sen1 not in self.sensorliste: raise("Ungültige Sensornummer")
        #Wenn nicht, dann gebe eine Fehlermeldung und verlasse die Funktion
        except:
            messagebox.showerror(title = "Ungültige Eingabe", message = "Bitte geben Sie als Ursprungssensor die Zahl 1,2,3 oder 4 ein.")
            return
        #Prüfe ob die Eingegebene Sensornummer eine gültige Sensornummer ist
        try:
            sen2 = int(sen2)
            if sen2 not in self.sensorliste: raise("Ungültige Sensornummer")
        #Wenn nicht, dann gebe eine Fehlermeldung und verlasse die Funktion
        except:
            messagebox.showerror(title = "Ungültige Eingabe", message = "Bitte geben Sie als Abzuziehenden Sensor die Zahl 1,2,3 oder 4 ein.")
            return
        #Wenn die Darstellungsrate zu klein ist, dann gebe eine Fehlermeldung und verlasse die Funktion
        if darstellungsrate < self.min_darstellungsrate:
            messagebox.showerror(title = "Zu hohe Darstellungsrate", message = "Bitte geben Sie eine größere Zeit für die Darstellungsrate ein.")
            return
        #Wenn die Darstellungsrate größer als der Zeitraum ist, dann gebe eine Fehlermeldung und verlasse die Funktion
        if darstellungsrate > zeitraum * 60:
            messagebox.showerror(title = "Zu kleiner Zeitraum", message = "Bitte geben Sie eine Zeitraum der größer als die Darstellungsrate ist ein.")
            return
        #Wenn zwei gleiche Sensoren ausgewählt wurden, dann gebe eine Fehlermeldung und verlasse die Funktion
        if sen1 == sen2:
            messagebox.showerror(title = "Gleiche Sensoren", message = "Bitte wählen Sie unterschiedliche Sensoren aus.")
            return
        #Wenn alle Prüfung erfolgreich waren, dann gebe die Parameter weiter um die Messung zu starten
        self.Templogger.differenz_graph_starten(int(darstellungsrate), int(zeitraum), dateiname, int(protokollierungsrate), sen1, sen2, popup_window)

    #Funktion zum prüfen der Eingabeparameter für die Darstellung einer bestehenden Protokolldatei
    def daten_laden_eingabe_testen(self,popup_window,dateiname,pfad):
        #Wenn der Pfad None ist, dann...
        if pfad == None:
            pfad = dateiname #weise dem pfad, den dateipfad zu
            dateiname = dateiname.split('/')[-1] #ermittel den dateiname
        #Wenn nicht, dann setzte den pfad mit dem dateiname zu
        else:
            pfad = pfad + dateiname
        #Wenn die gewählte Datei nicht existiert, dann gebe eine Fehlermeldung aus und verlasse die Funktion
        if not os.path.exists(pfad):
            messagebox.showerror(title = "Ungültiger Dateipfad", message = "Bitte geben Sie einen gültigen Dateipfad ein.")
            return
        #Setze die Variablen auf None
        sen1=None
        sen2=None
        antwort = ""
        differenz_log = False #setzte die Flag um zu markieren das es sich um ein Temperaturprotokoll handelt
        kalibriert = True
        #Protokolldatei zum lesen öffnen
        with open(pfad, 'r') as datei:
            csv_zeilen = list(csv.reader(datei,delimiter=';')) #Inhalt der Protokolldatei in eine Liste speichern
            
        daten = csv_zeilen #setze die Daten auf die ausgelesenen Daten
        #Wenn in der Protokolldatei in der ersten Zeile am Start Differenztemperaturlogger steht, dann...
        if csv_zeilen[0][0][0:25] == "Differenztemperaturlogger":
            sen1 = csv_zeilen[1][0][20] #Ermittel die Differenzsensoren aus dem Protokoll 
            sen2 = csv_zeilen[1][0][31]
            #Prüfe ob die Protokolldaten unkalibriert sind, wenn ja dann setze die Flag zum markieren das es unkalibriert ist
            if csv_zeilen[0][0][25:39] == "(unkalibriert)":
                kalibriert = False
            daten = csv_zeilen[2:] #filtere den oberen Header aus den daten raus
            differenz_log = True #setzte die Flag um zu markieren das es sich um ein Differenztemperaturprotokoll handelt
        #Wenn in der Protokolldatei in der ersten Zeile am Start Temperaturlogger steht, dann...
        elif csv_zeilen[0][0][0:16] == "Temperaturlogger":
            #Prüfe ob die Protokolldaten unkalibriert sind, wenn ja dann setze die Flag zum markieren das es unkalibriert ist
            if csv_zeilen[0][0][17:31] == "(unkalibriert)":
                kalibriert = False
            daten = csv_zeilen[2:] #filtere den oberen Header aus den daten raus
        #Wenn nicht, dann...
        else:
            #Wenn die Protokolldatei nicht passen ist, dann...
            antwort = messagebox.askyesno(title="Fehlerhaftes Protokoll", message="Die Protokolldatei ist fehlerhaft.\nWollen Sie trotzdem versuche die Datei zu laden?") #Öffne ein Fenster und frage ob die Protokolldatei trotzdem geladen werden soll
            #Wenn die Messung nicht beendet werden soll, dann verlasse die Funktion
            if not antwort:
                return
            #Wenn die länge der Datensätze im Protokoll unter 4 liegt, dann setzte die Flag das es sich um ein Differenzprotokoll handelt
            if 1 < len(csv_zeilen[2]) < 4:
                differenz_log = True
        #Wenn der Header der 2. Zeile des Protokolls passt, dann...
        if csv_zeilen[1][0][0:19] != "Zeitstempel, Sensor":
            if antwort == "":
                antwort = messagebox.askyesno(title="Fehlerhaftes Protokoll", message="Die Protokolldatei ist fehlerhaft.\nWollen Sie trotzdem versuche die Datei zu laden?") #Öffne ein Fenster und frage ob die Protokolldatei trotzdem geladen werden soll
                #Wenn die Messung beendet werden soll, dann beende die Messung, wenn nicht dann verlasse die Funktion
                if not antwort:
                    return
                #Wenn die länge der Datensätze im Protokoll unter 4 liegt, dann setzte die Flag das es sich um ein Differenzprotokoll handelt
            if 1 < len(csv_zeilen[2]) < 4:
                differenz_log = True
            
        popup_window.destroy() #Pop Up Fenster schließen
        #Rufe die Funktion zum darstellen der Protokolldaten und des Protokollgraphen
        self.show_protokoll_data(daten,dateiname,differenz_log,sen1,sen2,kalibriert)
        self.show_protokoll_graph(csv_zeilen,differenz_log,dateiname,sen1,sen2,kalibriert)

    #Funktion zum prüfen der Eingabeparameter für die Berechnung und Darstellung eines Differenztemperaturgraphen einer bestehenden Protokolldatei
    def daten_differenz_eingabe_testen(self,popup_window,dateiname,pfad,sen1,sen2):
        antwort = ""
        #Wenn der Pfad None ist, dann...
        if pfad == None:
            pfad = dateiname #weise dem pfad, den dateipfad zu
            dateiname = dateiname.split('/')[-1] #ermittel den dateiname
        #Wenn nicht, dann setzte den pfad mit dem dateiname zu
        else:
            pfad = pfad + dateiname
        #Prüfe ob die Eingegebene Sensornummer eine gültige Sensornummer ist
        try:
            sen1 = int(sen1)
            if sen1 not in self.sensorliste: raise("Ungültige Sensornummer")
        #Wenn nicht, dann gebe eine Fehlermeldung und verlasse die Funktion
        except:
            messagebox.showerror(title = "Ungültige Eingabe", message = "Bitte geben Sie als Ursprungssensor die Zahl 1,2,3 oder 4 ein.")
            return
        #Prüfe ob die Eingegebene Sensornummer eine gültige Sensornummer ist
        try:
            sen2 = int(sen2)
            if sen2 not in self.sensorliste: raise("Ungültige Sensornummer")
        #Wenn nicht, dann gebe eine Fehlermeldung und verlasse die Funktion
        except:
            messagebox.showerror(title = "Ungültige Eingabe", message = "Bitte geben Sie als Abzuziehenden Sensor die Zahl 1,2,3 oder 4 ein.")
            return
        #Wenn die gewählte Datei nicht existiert, dann gebe eine Fehlermeldung aus und verlasse die Funktion
        if not os.path.exists(pfad):
            messagebox.showerror(title = "Ungültiger Dateipfad", message = "Bitte geben Sie einen gültigen Dateipfad ein.")
            return
        #Protokolldatei zum lesen öffnen
        with open(pfad, 'r') as datei:
            csv_zeilen = list(csv.reader(datei,delimiter=';')) #Inhalt der Protokolldatei in eine Liste speichern
            #Wenn in der Protokolldatei in der ersten Zeile der erste Buchstabe ein "D" ist, dann zeige ein Fenster mit einer Fehlermeldung und verlasse die Funktion
        kalibriert = True
        daten = csv_zeilen #setze die Daten auf die ausgelesenen Daten
        #Wenn in der Protokolldatei in der ersten Zeile am Start Differenztemperaturlogger steht, dann öffne eine Fehlermeldung, da aus einem Differenzlog kein Differenzgraph gebildet werden kann
        if csv_zeilen[0][0][0:25] == "Differenztemperaturlogger":
            messagebox.showerror(title = "Ungeeignete Protokolldatei", message = "Es kann kein Differenzgraph aus einer Protokolldatei einer Differenztemperaturmessung erstellt werden.")
            return
        #Wenn in der Protokolldatei in der ersten Zeile am Start Temperaturlogger steht, dann...
        elif csv_zeilen[0][0][0:16] == "Temperaturlogger":
            #Prüfe ob die Protokolldaten unkalibriert sind, wenn ja dann setze die Flag zum markieren das es unkalibriert ist
            if csv_zeilen[0][0][17:31] == "(unkalibriert)":
                kalibriert = False
            daten = csv_zeilen[2:] #filtere den oberen Header aus den daten raus
        #Wenn nicht, dann...
        else:
            #Wenn die Protokolldatei nicht passen ist, dann...
            antwort = messagebox.askyesno(title="Fehlerhaftes Protokoll", message="Die Protokolldatei ist fehlerhaft.\nWollen Sie trotzdem versuche die Datei zu laden?") #Öffne ein Fenster und frage ob die Protokolldatei trotzdem geladen werden soll
            #Wenn die Messung nicht beendet werden soll, dann verlasse die Funktion
            if not antwort:
                return

        #Wenn der Header der 2. Zeile des Protokolls passt, dann...
        if csv_zeilen[1][0][0:19] != "Zeitstempel, Sensor":
            if antwort == "":
                antwort = messagebox.askyesno(title="Fehlerhaftes Protokoll", message="Die Protokolldatei ist fehlerhaft.\nWollen Sie trotzdem versuche die Datei zu laden?") #Öffne ein Fenster und frage ob die Protokolldatei trotzdem geladen werden soll
                #Wenn die Messung beendet werden soll, dann beende die Messung, wenn nicht dann verlasse die Funktion
                if not antwort:
                    return

        popup_window.destroy() #Pop Up Fenster schließen
        self.show_protokoll_differenz(daten,dateiname,sen1,sen2,kalibriert)
        self.show_protokoll_differenz_graph(csv_zeilen[2:],dateiname,sen1,sen2,kalibriert)
    
    #Funktion zum Öffnen eines Fensters zum Durchsuchen nach einer Datei
    def datei_oeffnen(self,datei_liste,combobox):
        dateipfad = filedialog.askopenfile(initialdir=self.Templogger.programm_pfad+"/Saves") #Öffnen des Fensters zum Durchsuchen nach einer Datei
        #Wenn keine Datei ausgewählt wurde, die Funktion wieder verlassen
        if dateipfad == None:
            return
        datei_liste.append(dateipfad.name) #Ausgewählte Datei mit Pfad der Liste für die Combobox hinzufügen
        combobox.configure(values=datei_liste) #Dateiliste der Combobox aktuallisieren
        #Ausgewählte Datei in der Combobox auswählen
        combobox.set(datei_liste[-1])

    #Funktion zum Öffnen eines Pop Up Fensters zur Eingabe der Messparameter für eine Echtzeittemperaturmessung
    def live_graph_popup(self):
        dateiname = None #Nur Darstellung daher wird kein Dateiname benötigt
        protokollierung = 0 #Nur Darstellung daher soll die Protokollierung deaktiviert sein
        protokollierungsrate = 0 #Nur Darstellung daher wird keine Protokollierungsrate benötigt
        darstellungsrate_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen der Darstellungsrate
        zeitraum_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen des Zeitraums

        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry("570x200") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-570)/2, y + (self.root.winfo_height()-200)/2)) #Position des Pop Up Fensters festlegen
        popup_window.wm_transient(self.root)
        popup_window.title("Einstellungen für die Darstellung") #Titel des Pop Up Fensters festlegen
        
        #Label und Spinbox für die Darstellungsrate erstellen und platzieren
        darstellungsrate_label = tk.Label(popup_window, text="Darstellungsrate in Sekunden zur Darstellung von Messpunkten: (Min. 4 Sek.)", pady=10, padx=20)
        darstellungsrate_label.pack()
        darstellungsrate = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=self.min_darstellungsrate,to=9999999999999999999999,textvariable=darstellungsrate_var)
        darstellungsrate.pack()
        darstellungsrate.focus() #Spinbox für die Darstellungsrate fokusieren
        #Label und Spinbox für den Zeitraum erstellen und platzieren
        zeitraum_label = tk.Label(popup_window, text="Abzubildender Zeitraum in Minuten:", pady=10, padx=20)
        zeitraum_label.pack()
        zeitraum = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=1,to=9999999999999999999999,textvariable=zeitraum_var)
        zeitraum.pack()

        #Funktion zum aufrufen der Prüffunktion der Eingabeparameter
        def aufruf_zum_testen():
            self.live_graph_eingabe_testen(darstellungsrate.get(), zeitraum.get(), dateiname, protokollierung, protokollierungsrate, popup_window)
        
        #Buttons zum Bestätigen oder Abbrechen der Eingabe erstellen und platzieren
        button_frame = tk.Frame(popup_window)
        button_frame.pack(pady=(7,0))
        okbutton = tk.Button(button_frame, text="Bestätigen", command=aufruf_zum_testen, height=2, width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame, text="Abbrechen", command = popup_window.destroy, height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)

        #Bei dem Ereignis das die Enter Taste gedrückt wurde die Funktion zum Prüfen der Eingabeparameter aufrufen
        darstellungsrate.bind("<Return>", lambda _: aufruf_zum_testen())
        zeitraum.bind("<Return>", lambda _: aufruf_zum_testen())
        #Bei dem Ereignis das die Escape Taste gedrückt wurde die soll das Fenster geschlossen werden
        popup_window.bind("<Escape>", lambda _:popup_window.destroy())
        
    #Funktion zum Öffnen eines Pop Up Fensters zur Eingabe der Mess- und Protokollierungsparameter für eine Echtzeittemperaturmessung
    def live_graph_protokoll_static_popup(self):
        protokollierung = 1 #Protokollierung soll aktiviert werden
        protokollierungs_darstellungs_rate_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen der Darstellungs- und Protokollierungsrate
        zeitraum_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen des Zeitraumes

        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry("580x270")#Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-580)/2, y + (self.root.winfo_height()-270)/2)) #Position des Pop Up Fensters festlegen
        # Keep the popup_window in front of the root window
        popup_window.wm_transient(self.root)
        popup_window.title("Einstellungen für Darstellung und Protokollierung") #Titel des Pop Up Fensters festlegen

        #Label und Spinbox für den Darstellungs- und Protokollierungsrate erstellen und platzieren
        protokollierungsrate_label = tk.Label(popup_window, text="Darstellungs- und Protokollierungsrate in Sekunden von Messdaten: (Min. 4 Sek.)", pady=10)
        protokollierungsrate_label.pack()
        protokollierungs_darstellungs_rate = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=self.min_darstellungsrate,to=9999999999999999999999,textvariable=protokollierungs_darstellungs_rate_var)
        protokollierungs_darstellungs_rate.pack()
        protokollierungs_darstellungs_rate.focus() #Spinbox der Darstellungs- und Protokollierungsrate fokusieren
        #Label und Spinbox für den Zeitraum erstellen und platzieren
        zeitraum_label = tk.Label(popup_window, text="Abzubildender Zeitraum in Minuten:", pady=10, padx=20)
        zeitraum_label.pack()
        zeitraum = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=1,to=9999999999999999999999,textvariable=zeitraum_var)
        zeitraum.pack()
        #Label und Eingabefeld für den Dateiname erstellen und platzieren
        datei_label = tk.Label(popup_window, text="Name der Protokolldatei (Speicherort: {}/Saves)".format(self.Templogger.programm_pfad), pady=10, padx=20)
        datei_label.pack()
        dateiname = tk.Entry(popup_window, width=40, bg="light yellow")
        dateiname.insert(tk.END,"<<Erster Zeitstempel>>")
        dateiname.pack()

        #Funktion zum aufrufen der Prüffunktion der Eingabeparameter
        def aufruf_zum_testen():
            self.live_graph_eingabe_testen(protokollierungs_darstellungs_rate.get(), zeitraum.get(), dateiname.get(), protokollierung, protokollierungs_darstellungs_rate.get(), popup_window)

        #Buttons zum Bestätigen oder Abbrechen der Eingabe erstellen und platzieren
        button_frame = tk.Frame(popup_window)
        button_frame.pack(pady=(7,0))
        okbutton = tk.Button(button_frame, text="Bestätigen", command=aufruf_zum_testen, height=2, width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame, text="Abbrechen", command = popup_window.destroy, height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)

        #Beim Enter drücken die Funktion zum Prüfen der Eingabeparameter aufrufen
        protokollierungs_darstellungs_rate.bind("<Return>", lambda _: aufruf_zum_testen())
        zeitraum.bind("<Return>", lambda _: aufruf_zum_testen())
        dateiname.bind("<Return>", lambda _: aufruf_zum_testen())
        
        #Beim anklicken des Elements, die Bildschirmtastatur öffnen
        dateiname.bind("<Button-1>",lambda _: self.open_keyboard())

        #Beim Escape drücken soll das Fenster geschlossen werden
        popup_window.bind("<Escape>", lambda _: popup_window.destroy())

    #Funktion zum Öffnen eines Pop Up Fensters zur Eingabe der Mess- und Protokollierungsparameter für eine Echtzeittemperaturmessung
    def live_graph_protokoll_popup(self):
        protokollierung = 1 #Protokollierung soll aktiviert werden
        protokollierungsrate_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen der Protokollierungsrate
        darstellungsrate_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen der Darstellungsrate
        zeitraum_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen des Zeitraums

        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry("675x320") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-675)/2, y + (self.root.winfo_height()-320)/2)) #Position des Pop Up Fensters festlegen
        # Keep the popup_window in front of the root window
        popup_window.wm_transient(self.root)
        popup_window.title("Einstellungen für Darstellung und Protokollierung") #Titel des Pop Up Fensters festlegen

        #Label und Spinbox für die Protokollierungsrate erstellen und platzieren
        protokollierungsrate_label = tk.Label(popup_window, text="Protokollierungsrate in Sekunden zur Protokollierung von Messpunkten:",pady=10)
        protokollierungsrate_label.pack()
        protokollierungsrate = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=1,to=9999999999999999999999,textvariable=protokollierungsrate_var)
        protokollierungsrate.pack()
        protokollierungsrate.focus()
        #Label und Spinbox für die Darstellungsrate erstellen und platzieren
        darstellungsrate_label = tk.Label(popup_window, text="Darstellungsrate in Sekunden zur Darstellung von Messpunkten: (Min. 4 Sek.)",pady=10)
        darstellungsrate_label.pack()
        darstellungsrate = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=self.min_darstellungsrate,to=9999999999999999999999,textvariable=darstellungsrate_var)
        darstellungsrate.pack()
        #Label und Spinbox für den Zeitraum erstellen und platzieren
        zeitraum_label = tk.Label(popup_window, text="Abzubildender Zeitraum in Minuten:", pady=10, padx=20)
        zeitraum_label.pack()
        zeitraum = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=1,to=9999999999999999999999,textvariable=zeitraum_var)
        zeitraum.pack()
        #Label und Eingabefeld für den Dateiname erstellen und platzieren
        datei_label = tk.Label(popup_window, text="Name der Protokolldatei (Speicherort: {}/Saves):".format(self.Templogger.programm_pfad), pady=10,padx=20)
        datei_label.pack()
        dateiname = tk.Entry(popup_window, width=40, bg="light yellow")
        dateiname.insert(tk.END,"<<Erster Zeitstempel>>")
        dateiname.pack()

        #Funktion zum aufrufen der Prüffunktion der Eingabeparameter
        def aufruf_zum_testen():
            self.live_graph_eingabe_testen(darstellungsrate.get(), zeitraum.get(), dateiname.get(), protokollierung, protokollierungsrate.get(), popup_window)

        #Buttons zum Bestätigen oder Abbrechen der Eingabe erstellen und platzieren
        button_frame = tk.Frame(popup_window)
        button_frame.pack(pady=(7,0))
        okbutton = tk.Button(button_frame, text="Bestätigen", command=aufruf_zum_testen, height=2, width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame, text="Abbrechen", command = popup_window.destroy, height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)

        #Beim Enter drücken die Funktion zum Prüfen der Eingabeparameter aufrufen
        protokollierungsrate.bind("<Return>", lambda _: aufruf_zum_testen())
        darstellungsrate.bind("<Return>", lambda _: aufruf_zum_testen())
        zeitraum.bind("<Return>", lambda _: aufruf_zum_testen())
        dateiname.bind("<Return>", lambda _: aufruf_zum_testen())
        
        #Beim anklicken des Elements, die Bildschirmtastatur öffnen
        dateiname.bind("<Button-1>",lambda _: self.open_keyboard())

        #Beim Escape drücken das Fenster schließen
        popup_window.bind("<Escape>", lambda _:popup_window.destroy())

    #Funktion zum Öffnen eines Pop Up Fensters zur Eingabe der Messparameter für eine Differenztemperaturmessung
    def differenz_graph_popup(self):
        dateiname = None #Nur Darstellung daher wird kein Dateiname benötigt
        protokollierung = 0 #Nur Darstellung daher wird keine Protokollierungsrate benötigt
        protokollierungsrate = 0 #Nur Darstellung daher wird keine Protokollierungsrate benötigt
        darstellungsrate_var = tk.StringVar(value=5)  #Variable für die Spinbox zum auswählen der Darstellungsrate
        zeitraum_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen des Zeitraums

        #Hintergrundfarbe der Combobox ändern
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", fieldbackground= "light yellow")

        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry("580x320") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-580)/2, y + (self.root.winfo_height()-320)/2)) #Position des Pop Up Fensters festlegen
        # Keep the popup_window in front of the root window
        popup_window.wm_transient(self.root)
        popup_window.title("Einstellungen für die Darstellung") #Titel des Pop Up Fensters festlegen
        
        #Label und Spinbox für die Darstellungsrate erstellen und platzieren
        darstellungsrate_label = tk.Label(popup_window, text="Darstellungsrate in Sekunden zur Darstellung von Messpunkten: (Min. 4 Sek.)", pady=10, padx=20)
        darstellungsrate_label.pack()
        darstellungsrate = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=self.min_darstellungsrate,to=9999999999999999999999,textvariable=darstellungsrate_var)
        darstellungsrate.pack()
        darstellungsrate.focus()
        #Label und Spinbox für den Zeitraum erstellen und platzieren
        zeitraum_label = tk.Label(popup_window, text="Abzubildender Zeitraum in Minuten:", pady=10, padx=20)
        zeitraum_label.pack()
        zeitraum = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=1,to=9999999999999999999999,textvariable=zeitraum_var)
        zeitraum.pack()
        #Label und Combobox zur Sensorauswahl erstellen und platzieren
        sen1_label = tk.Label(popup_window, text="Ursprungssensor:", pady=10, padx=20)
        sen1_label.pack()
        sen1 = ttk.Combobox(popup_window,values=self.sensorliste)
        sen1.set(1) #Als Standardwert der Combobox das erste Element auswählen
        sen1.pack()
        #Label und Combobox zur Sensorauswahl erstellen und platzieren
        sen2_label = tk.Label(popup_window, text="Abzuziehender Sensor:", pady=10, padx=20)
        sen2_label.pack()
        sen2 = ttk.Combobox(popup_window,values=self.sensorliste)
        sen2.set(2) #Als Standardwert der Combobox das zweite Element auswählen
        sen2.pack()

        #Funktion zum aufrufen der Prüffunktion der Eingabeparameter
        def aufruf_zum_testen():
            self.differenz_graph_eingabe_testen(darstellungsrate.get(), zeitraum.get(), dateiname,protokollierung, protokollierungsrate, sen1.get(), sen2.get(), popup_window)

        #Buttons zum Bestätigen oder Abbrechen der Eingabe erstellen und platzieren
        button_frame = tk.Frame(popup_window)
        button_frame.pack(pady=(7,0))
        okbutton = tk.Button(button_frame, text="Bestätigen", command=aufruf_zum_testen, height=2, width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame, text="Abbrechen", command = popup_window.destroy, height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)
        
        #Beim Enter drücken die Funktion zum Prüfen der Eingabeparameter aufrufen
        darstellungsrate.bind("<Return>", lambda _: aufruf_zum_testen())
        zeitraum.bind("<Return>", lambda _: aufruf_zum_testen())
        sen1.bind("<Return>", lambda _: aufruf_zum_testen())
        sen2.bind("<Return>", lambda _: aufruf_zum_testen())

        #Beim Escape drücken das Fenster schließen
        popup_window.bind("<Escape>", lambda _: popup_window.destroy())
 
    #Funktion zum Öffnen eines Pop Up Fensters zur Eingabe der Mess- und Protokollierungsparameter für eine Differenztemperaturmessung
    def differenz_graph_protokoll_static_popup(self):
        protokollierung = 1 #Protokollierung soll aktiviert werden
        protokollierungs_darstellungs_rate_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen der Darstellungs- und Protokollierungsrate
        zeitraum_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen des Zeitraums
        
        #Hintergrundfarbe der Combobox ändern
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", fieldbackground= "light yellow")

        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry("590x380") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-590)/2, y + (self.root.winfo_height()-380)/2)) #Position des Pop Up Fensters festlegen
        # Keep the popup_window in front of the root window
        popup_window.wm_transient(self.root)
        popup_window.title("Einstellungen für Darstellung und Protokollierung") #Titel des Pop Up Fensters festlegen

        #Label und Spinbox für den Darstellungs- und Protokollierungsrate erstellen und platzieren
        protokollierungs_darstellungs_rate_label = tk.Label(popup_window, text="Darstellungs- und Protokollierungsrate in Sekunden von Messdaten: (Min. 4 Sek.)",pady=10, padx=20)
        protokollierungs_darstellungs_rate_label.pack()
        protokollierungs_darstellungs_rate = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=self.min_darstellungsrate,to=9999999999999999999999,textvariable=protokollierungs_darstellungs_rate_var)
        protokollierungs_darstellungs_rate.pack()
        protokollierungs_darstellungs_rate.focus()
        #Label und Spinbox für den Zeitraum erstellen und platzieren
        zeitraum_label = tk.Label(popup_window, text="Abzubildender Zeitraum in Minuten:", pady=10, padx=20)
        zeitraum_label.pack()
        zeitraum = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=1,to=9999999999999999999999,textvariable=zeitraum_var)
        zeitraum.pack()
        #Label und Eingabefeld für den Dateiname erstellen und platzieren
        dateiname_label = tk.Label(popup_window, text="Name der Protokolldatei (Speicherort: {}/Saves):".format(self.Templogger.programm_pfad), pady=10,padx=20)
        dateiname_label.pack()
        dateiname = tk.Entry(popup_window, width=40, bg="light yellow")
        dateiname.insert(tk.END,"<<Erster Zeitstempel>>")
        dateiname.pack()
        #Label und Combobox zur Sensorauswahl erstellen und platzieren
        sen1_label = tk.Label(popup_window, text="Ursprungssensor", pady=10, padx=20)
        sen1_label.pack()
        sen1 = ttk.Combobox(popup_window,values=self.sensorliste)
        sen1.set(1) #Als Standardwert der Combobox das erste Element auswählen
        sen1.pack()
        #Label und Combobox zur Sensorauswahl erstellen und platzieren
        sen2_label = tk.Label(popup_window, text="Abzuziehender Sensor", pady=10, padx=20)
        sen2_label.pack()
        sen2 = ttk.Combobox(popup_window,values=self.sensorliste)
        sen2.set(2) #Als Standardwert der Combobox das zweite Element auswählen
        sen2.pack()

        #Funktion zum aufrufen der Prüffunktion der Eingabeparameter
        def aufruf_zum_testen():
            self.differenz_graph_eingabe_testen(protokollierungs_darstellungs_rate.get(), zeitraum.get(), dateiname.get(),protokollierung, protokollierungs_darstellungs_rate.get(), sen1.get(), sen2.get(), popup_window)

        #Buttons zum Bestätigen oder Abbrechen der Eingabe erstellen und platzieren
        button_frame = tk.Frame(popup_window)
        button_frame.pack(pady=(7,0))
        okbutton = tk.Button(button_frame, text="Bestätigen", command=aufruf_zum_testen, height=2, width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame, text="Abbrechen", command = popup_window.destroy, height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)

        #Beim Enter drücken die Funktion zum Prüfen der Eingabeparameter aufrufen
        protokollierungs_darstellungs_rate.bind("<Return>", lambda _: aufruf_zum_testen())
        zeitraum.bind("<Return>", lambda _: aufruf_zum_testen())
        dateiname.bind("<Return>", lambda _: aufruf_zum_testen())
        sen1.bind("<Return>", lambda _: aufruf_zum_testen())
        sen2.bind("<Return>", lambda _: aufruf_zum_testen())
        
        #Beim anklicken des Elements, die Bildschirmtastatur öffnen
        dateiname.bind("<Button-1>",lambda _: self.open_keyboard())

        #Beim Escape drücken das Fenster schließen
        popup_window.bind("<Escape>", lambda _: popup_window.destroy())

    #Funktion zum Öffnen eines Pop Up Fensters zur Eingabe der Mess- und Protokollierungsparameter für eine Differenztemperaturmessung
    def differenz_graph_protokoll_popup(self):
        protokollierung = 1 #Protokollierung soll aktiviert werden
        protokollierungsrate_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen der Protokollierungsrate
        darstellungsrate_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen der Darstellungsrate
        zeitraum_var = tk.StringVar(value=5) #Variable für die Spinbox zum auswählen des Zeitraums
        
        #Hintergrundfarbe der Combobox ändern
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", fieldbackground= "light yellow")

        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry("675x440") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-675)/2, y + (self.root.winfo_height()-440)/2)) #Position des Pop Up Fensters festlegen
        # Keep the popup_window in front of the root window
        popup_window.wm_transient(self.root)
        popup_window.title("Eingabe Parameter Differenzengraf mit Protokoll") #Titel des Pop Up Fensters festlegen

        #Label und Spinbox für die Protokollierungsrate erstellen und platzieren
        protokollierungsrate_label = tk.Label(popup_window, text="Protokollierungsrate in Sekunden zur Protokollierung von Messpunkten:",pady=10, padx=20)
        protokollierungsrate_label.pack()
        protokollierungsrate = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=1,to=9999999999999999999999,textvariable=protokollierungsrate_var)
        protokollierungsrate.pack()
        protokollierungsrate.focus()
        #Label und Spinbox für die Darstellungsrate erstellen und platzieren
        darstellungsrate_label = tk.Label(popup_window, text="Darstellungsrate in Sekunden zur Darstellung von Messpunkten: (Min. 4 Sek.)", pady=10, padx=20)
        darstellungsrate_label.pack()
        darstellungsrate = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=self.min_darstellungsrate,to=9999999999999999999999,textvariable=darstellungsrate_var)
        darstellungsrate.pack()
        #Label und Spinbox für den Zeitraum erstellen und platzieren
        zeitraum_label = tk.Label(popup_window, text="Abzubildender Zeitraum in Minuten:", pady=10, padx=20)
        zeitraum_label.pack()
        zeitraum = tk.Spinbox(popup_window,bg="light yellow",width=30,from_=1,to=9999999999999999999999,textvariable=zeitraum_var)
        zeitraum.pack()
        #Label und Eingabefeld für den Dateiname erstellen und platzieren
        dateiname_label = tk.Label(popup_window, text="Name der Protokolldatei (Speicherort: {}/Saves):".format(self.Templogger.programm_pfad), pady=10,padx=20)
        dateiname_label.pack()
        dateiname = tk.Entry(popup_window, width=40, bg="light yellow")
        dateiname.insert(tk.END,"<<Erster Zeitstempel>>")
        dateiname.pack()
        #Label und Combobox zur Sensorauswahl erstellen und platzieren
        sen1_label = tk.Label(popup_window, text="Ursprungssensor", pady=10, padx=20)
        sen1_label.pack()
        sen1 = ttk.Combobox(popup_window,values=self.sensorliste)
        sen1.set(1) #Als Standardwert der Combobox das erste Element auswählen
        sen1.pack()
        #Label und Combobox zur Sensorauswahl erstellen und platzieren
        sen2_label = tk.Label(popup_window, text="Abzuziehender Sensor", pady=10, padx=20)
        sen2_label.pack()
        sen2 = ttk.Combobox(popup_window,values=self.sensorliste)
        sen2.set(2) #Als Standardwert der Combobox das zweite Element auswählen
        sen2.pack()

        #Funktion zum aufrufen der Prüffunktion der Eingabeparameter
        def aufruf_zum_testen():
            self.differenz_graph_eingabe_testen(darstellungsrate.get(), zeitraum.get(), dateiname.get(),protokollierung, protokollierungsrate.get(), sen1.get(), sen2.get(), popup_window)
            
        #Buttons zum Bestätigen oder Abbrechen der Eingabe erstellen und platzieren
        button_frame = tk.Frame(popup_window)
        button_frame.pack(pady=(7,0))
        okbutton = tk.Button(button_frame, text="Bestätigen", command=aufruf_zum_testen, height=2, width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame, text="Abbrechen", command = popup_window.destroy, height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)

        #Beim Enter drücken die Funktion zum Prüfen der Eingabeparameter aufrufen
        protokollierungsrate.bind("<Return>", lambda _: aufruf_zum_testen())
        darstellungsrate.bind("<Return>", lambda _: aufruf_zum_testen())
        zeitraum.bind("<Return>", lambda _: aufruf_zum_testen())
        dateiname.bind("<Return>", lambda _: aufruf_zum_testen())
        sen1.bind("<Return>", lambda _: aufruf_zum_testen())
        sen2.bind("<Return>", lambda _: aufruf_zum_testen())
        
        #Beim anklicken des Elements, die Bildschirmtastatur öffnen
        dateiname.bind("<Button-1>",lambda _: self.open_keyboard())

        #Beim Escape drücken das Fenster schließen
        popup_window.bind("<Escape>", lambda _: popup_window.destroy())

    #Funktion zum Öffnen eines Pop Up Fensters zur Eingabe von Parametern zum Laden und darstellen einer Protokolldatei
    def protokoll_daten_popup(self):
        #Hintergrundfarbe der Combobox ändern
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", fieldbackground= "light yellow")

        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry("450x150") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-450)/2, y + (self.root.winfo_height()-150)/2)) #Position des Pop Up Fensters festlegen
        popup_window.wm_transient(self.root)
        popup_window.title("Protokolldaten laden") #Titel des Pop Up Fensters festlegen

        datei_liste = [datei.name for datei in os.scandir(self.Templogger.programm_pfad + "/Saves") if datei.is_file()] #Ermitteln welche Dateien im /Saves Ordner sind
        datei_liste.sort()
        combo_box_liste = datei_liste[:] #Ermittelte Liste der Dateinamen kopieren
        #Label für die Beschriftung der Dateiname eingabe erstellen und platzieren
        dateilabel = tk.Label(popup_window, text="Dateipfad und Name der .csv Datei:", pady=10, padx=20)
        dateilabel.pack()
        #Erstellen und platzieren eines Frames zur anordnung der Combobox und des Durchsuchen Buttons
        dateipfad_frame = tk.Frame(popup_window)
        dateipfad_frame.pack()
        #Combobox erstellen und platzieren mit der Liste der ermittelten Dateien im /Saves Ordner
        dateipfad = ttk.Combobox(dateipfad_frame,values=combo_box_liste,width=40)
        dateipfad.pack(side=tk.LEFT)
        #Button erstellen und platzieren zum suchen einer Datei an einem anderen Ort und zum hinzufügen in die Liste der Combobox
        datei_auswaehlen = tk.Button(dateipfad_frame,text="...",width=1,height=1,command=lambda: self.datei_oeffnen(combo_box_liste,dateipfad))
        datei_auswaehlen.pack(side=tk.LEFT)

        def aufruf():
            pfad = None
            dateiname = dateipfad.get() #gewählten Dateiname bzw. Dateipfad aus der Combobox abfragen
            #Wenn der Dateiname aus dem /Saves Ordner ist, dann...
            if dateiname in datei_liste:
                pfad = self.Templogger.programm_pfad + "/Saves/" #Füge zu dem Dateiname den Pfad des /Saves Ordner hinzu
            self.daten_laden_eingabe_testen(popup_window,dateiname,pfad)

        button_frame = tk.Frame(popup_window)
        button_frame.pack(pady=(7,0))
        okbutton = tk.Button(button_frame, text="Bestätigen", command=aufruf,height=2, width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame, text="Abbrechen", command=popup_window.destroy, height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)
        
        #Beim Enter drücken die Funktion zum Prüfen der Eingabeparameter aufrufen
        dateipfad.bind("<Return>", lambda _: aufruf)

        #Beim Escape drücken das Fenster schließen
        popup_window.bind("<Escape>", lambda _:popup_window.destroy())

    #Funktion zum Öffnen eines Pop Up Fensters zur Eingabe von Parametern zum Laden einer Protokolldatei und dem bilden eines Differenztemperaturgraphen
    def Protokolldaten_differenz_popup(self):
        #Hintergrundfarbe der Combobox ändern
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", fieldbackground= "light yellow")

        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry("450x260") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-450)/2, y + (self.root.winfo_height()-260)/2)) #Position des Pop Up Fensters festlegen
        popup_window.wm_transient(self.root)
        popup_window.title("Protokolldaten laden") #Titel des Pop Up Fensters festlegen
    
        datei_liste = [datei.name for datei in os.scandir(self.Templogger.programm_pfad + "/Saves") if datei.is_file()] #Ermitteln welche Dateien im /Saves Ordner sind
        datei_liste.sort()
        combo_box_liste = datei_liste[:] #Ermittelte Liste der Dateinamen kopieren
        #Label für die Beschriftung der Dateiname eingabe erstellen und platzieren
        dateipfad_label = tk.Label(popup_window, text="Dateipfad und Name der .csv Datei:", pady=10, padx=20)
        dateipfad_label.pack()
        #Erstellen und platzieren eines Frames zur anordnung der Combobox und des Durchsuchen Buttons
        dateipfad_frame = tk.Frame(popup_window)
        dateipfad_frame.pack()
        #Combobox erstellen und platzieren mit der Liste der ermittelten Dateien im /Saves Ordner
        dateipfad = ttk.Combobox(dateipfad_frame,values=combo_box_liste,width=40)
        dateipfad.pack(side=tk.LEFT)
        #Button erstellen und platzieren zum suchen einer Datei an einem anderen Ort und zum hinzufügen in die Liste der Combobox
        datei_auswaehlen = tk.Button(dateipfad_frame,text="...",width=1,height=1,command=lambda: self.datei_oeffnen(combo_box_liste,dateipfad))
        datei_auswaehlen.pack(side=tk.LEFT)
        #Erstellen und platzieren eines Labels zur Beschriftung
        sen1_label = tk.Label(popup_window, text="Ursprungssensor:", pady=10, padx=20)
        sen1_label.pack()
        sensorliste = [1,2,3,4]
        #Combobox erstellen und platzieren zur Auswahl der Sensornummer
        sen1 = tk.ttk.Combobox(popup_window,values=sensorliste)
        sen1.pack()
        sen1.set(1) #Als Standart das erste Element ausgewählt
        #Erstellen und platzieren eines Labels zur Beschriftung
        sen2_label = tk.Label(popup_window, text="Abzuziehende Sensor:", pady=10, padx=20)
        sen2_label.pack()
        #Combobox erstellen und platzieren zur Auswahl der Sensornummer
        sen2 = tk.ttk.Combobox(popup_window,values=sensorliste)
        sen2.pack()
        sen2.set(2) #Als Standart das zweite Element ausgewählt

        def aufruf():
            pfad = None
            dateiname = dateipfad.get() #gewählten Dateiname bzw. Dateipfad aus der Combobox abfragen
            #Wenn der Dateiname aus dem /Saves Ordner ist, dann...
            if dateiname in datei_liste:
                pfad = self.Templogger.programm_pfad + "/Saves/" #Füge zu dem Dateiname den Pfad des /Saves Ordner hinzu
            self.daten_differenz_eingabe_testen(popup_window,dateiname,pfad,sen1.get(),sen2.get())

        button_frame = tk.Frame(popup_window)
        button_frame.pack(pady=(7,0))
        okbutton = tk.Button(button_frame, text="Bestätigen", command=aufruf, height=2, width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame, text="Abbrechen", command=popup_window.destroy, height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)
    
        #Beim Enter drücken die Funktion zum Prüfen der Eingabeparameter aufrufen
        dateipfad.bind("<Return>", lambda _: aufruf)
        sen1.bind("<Return>", lambda _: aufruf)
        sen2.bind("<Return>", lambda _: aufruf)
        
        #Beim Escape drücken das Fenster schließen
        popup_window.bind("<Escape>", lambda _: popup_window.destroy())

    #Funktion zum Öffnen eines Pop Up Fensters zum anzeigen der Daten des Protokolls
    def show_protokoll_data(self,daten,dateiname,differenz_log,sen1,sen2,kalibriert):
        popup_window = Toplevel(self.root,bg="white") #Pop Up Fenster erzeugen
        popup_window.geometry("620x450") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-620)/2, y + (self.root.winfo_height()-450)/2)) #Position des Pop Up Fensters festlegen
        popup_window.title(dateiname + " Protokolldaten") #Titel des Pop Up Fensters festlegen
        #Wenn die Daten unkalibrierte Messwerte sind, dann erstelle ein Label mit dem Hinweise dazu
        if not kalibriert:
            kalibriert_label = tk.Label(popup_window,text="nicht kalibriert",fg="red",bg="white")
            kalibriert_label.pack()
        #Erstelle und platziere eine vertikale und horizontale Scrollbar für den Treeview
        scrollbar_v = tk.Scrollbar(popup_window)
        scrollbar_v.pack(side=tk.RIGHT,fill="y")
        scrollbar_h = tk.Scrollbar(popup_window,orient='horizontal')
        scrollbar_h.pack(side=tk.BOTTOM,fill="x")
        #Definiere die Spalten für den Treeview, in abhängigkeit der Protokollart
        if differenz_log:
            treeview_columns = ["Zeitstempel","Sensor1"]
        else:
            treeview_columns = ["Zeitstempel","Sensor1","Sensor2","Sensor3","Sensor4"]
        #Erstelle und platziere die Treeview
        treeview = ttk.Treeview(popup_window,columns=treeview_columns,show="headings",yscrollcommand=scrollbar_v.set,xscrollcommand=scrollbar_h.set)
        treeview.pack(fill=tk.BOTH,expand=True)
        #Definiere die Spaltenüberschriften des Treeview
        treeview.heading('Zeitstempel', text='Zeitstempel')
        #Definiere die Breite der Treeview Spalten
        treeview.column("Zeitstempel", minwidth=180,width=180,stretch=1)
        #Definiere die Spaltenüberschriften und die Spaltenbreite des Treeview in abhängigkeit der Protokollart
        if differenz_log:
            treeview.heading('Sensor1', text='Sensor {} - Sensor {}'.format(sen1,sen2))
            treeview.column("Sensor1", minwidth=306,width=102,stretch=1)
        else:
            treeview.heading('Sensor1', text='Sensor 1')
            treeview.column("Sensor1", minwidth=102,width=102,stretch=1)
            treeview.heading('Sensor2', text='Sensor 2')
            treeview.column("Sensor2",minwidth=102,width=102,stretch=1)
            treeview.heading('Sensor3', text='Sensor 3')
            treeview.column("Sensor3", minwidth=102,width=102,stretch=1)
            treeview.heading('Sensor4', text='Sensor 4')
            treeview.column("Sensor4", minwidth=102,width=102,stretch=1)
        #schreibe die Protokolldaten in den Treeview
        for zeile in daten:
            treeview.insert("", tk.END, values=zeile)
        #Weise den Scollbars die Steuerung des Treeview zu
        scrollbar_v.config(command=treeview.yview)
        scrollbar_h.config(command=treeview.xview)
    
    #Funktion zum Öffnen eines Pop Up Fensters zum anzeigen der Differenz des Protokolls
    def show_protokoll_differenz(self,daten,dateiname,sen1,sen2,kalibriert):
        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry("620x450") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.root.winfo_width()-620)/2, y + (self.root.winfo_height()-450)/2)) #Position des Pop Up Fensters festlegen
        popup_window.title(dateiname + " Protokolldaten") #Titel des Pop Up Fensters festlegen
        #Wenn die Daten unkalibrierte Messwerte sind, dann erstelle ein Label mit dem Hinweise dazu
        if not kalibriert:
            kalibriert_label = tk.Label(popup_window,text="nicht kalibriert",fg="red",bg="white")
            kalibriert_label.pack()
        #Erstelle und platziere eine vertikale und horizontale Scrollbar für den Treeview
        scrollbar_v = tk.Scrollbar(popup_window)
        scrollbar_v.pack(side=tk.RIGHT,fill="y")
        scrollbar_h = tk.Scrollbar(popup_window,orient='horizontal')
        scrollbar_h.pack(side=tk.BOTTOM,fill="x")
        #Definiere die Spalten für den Treeview
        treeview_columns = ["Zeitstempel","Differenz"]
        #Erstelle und platziere die Treeview
        treeview = ttk.Treeview(popup_window,columns=treeview_columns,show="headings",yscrollcommand=scrollbar_v.set,xscrollcommand=scrollbar_h.set)
        treeview.pack(fill=tk.BOTH,expand=True)
        #Definiere die Spaltenüberschriften des Treeview
        treeview.heading('Zeitstempel', text='Zeitstempel')
        treeview.column("Zeitstempel", minwidth=180,width=180,stretch=1)
        treeview.heading('Differenz', text='Sensor {} - Sensor {}'.format(sen1,sen2))
        treeview.column("Differenz", minwidth=306,width=102,stretch=1)
        #schreibe die Protokolldaten in den Treeview
        for zeile in daten:
            treeview.insert("", tk.END, values=[zeile[0],str(round(float(zeile[sen1].replace(",",".")) - float(zeile[sen2].replace(",",".")),3)).replace(".",",")])
        #Weise den Scollbars die Steuerung des Treeview zu
        scrollbar_v.config(command=treeview.yview)
        scrollbar_h.config(command=treeview.xview)

    #Funktion zum Öffnen eines Pop Up Fensters zum anzeigen des Graphen des Protokolls
    def show_protokoll_graph(self,daten,differenz_log,dateiname,sen1,sen2,kalibriert):
        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry('1024x680') #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        #x = self.root.winfo_x()
        #y = self.root.winfo_y()
        #popup_window.geometry("+%d+%d" % (x + 0, y + 0)) #Position des Pop Up Fensters festlegen
        popup_window.title(dateiname + " Protokollgraph") #Titel des Pop Up Fensters festlegen
        #Versuche das Protokoll zu lesen und darzustellen
        try:
            fig = plt.figure(figsize=(1,1))
            ax = fig.add_subplot(111) #Es soll nur ein Graph dargestellt werden
            canvas = FigureCanvasTkAgg(fig,master=popup_window)
        
            #Formatiere die X-Achse
            locator = mdates.AutoDateLocator(minticks=8, maxticks=12)
            formatter = mdates.DateFormatter('%Y.%m.%d %H:%M:%S')
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)
            fig.autofmt_xdate(rotation=15,bottom=0.15)
            #Zeige die Achsen an
            ax.axes.get_xaxis().set_visible(True)
            ax.axes.get_yaxis().set_visible(True)
            ax.grid(True) #Zeige das Graphgitter an
            #Definiere die Achsenbeschriftung
            ax.set_xlabel("Messzeitpunkt")
            ax.set_ylabel("Differenztemperatur in °C")

            #Listen für die auszulesenden Daten erstellen
            datumlist = np.array([])
            sensor1list = np.array([])
            sensor2list = np.array([])
            sensor3list = np.array([])
            sensor4list = np.array([])
            
            header = False #Flag zum markieren, dass die nächste Zeile die 2. Headerzeile ist
            fehler_flag = False #Flag zum markieren, dass es min. ein Fehler gab

            #Zeitstempel und Temperaturdaten aus der Protokolldatei den Listen zuweisen
            for zeile in daten:
                #Wenn Zeile die 2. Headerzeile ist, dann...
                if header:
                    header = False #setze die Flag zurück
                    #Versuche...
                    try:
                        datumlist = np.append(datumlist,datumlist[-1]+datetime.timedelta(seconds=1)) #einen Zeitstempel der Liste zuzufügen
                        sensor1list = np.append(sensor1list,None) #Füge der Liste einen None Wert hinzu
                        #Wenn es sich nicht um ein Differenztemperaturprotokoll handelt, dann weise den Listen jeweils einen None Wert hinzu
                        if not differenz_log:
                            sensor2list = np.append(sensor2list,None)
                            sensor3list = np.append(sensor3list,None)
                            sensor4list = np.append(sensor4list,None)
                    #Wenn es ein Fehler gab, dann mache nichts
                    except: None
                    continue #Führe die For Schleife mit dem nächsten Listenelement fort
                #Versuche der Liste den Zeitstempel mit dem Format hinzuzufügen
                try:
                    datumlist = np.append(datumlist,datetime.datetime.strptime(zeile[0],"%Y.%m.%d %H:%M:%S"))
                #Wenn es dabei ein Fehler gab, dann...
                except:
                    #Versuche das Format des Zeitstempels zu erkennen
                    try:
                        datumlist = np.append(datumlist,dateutil.parser.parse(zeile[0]))
                    #Wenn es ein Fehler gab, dann...
                    except:
                        #Wenn der Anfang der Zeile Differenztemperaturlogger oder Temperaturlogger ist, dann...
                        if zeile[0][0:25] == "Differenztemperaturlogger" or zeile[0][0:16] == "Temperaturlogger":
                            header = True #setze die Flag zum markieren das die nächste Zeile die 2. Headerzeile ist
                            continue #Führe die For Schleife mit dem nächsten Listenelement fort
                        fehler_flag = True #Wenn die Zeile mit etwas anderem startet, dann setze die Flag zum markieren, das es ein Fehler gab
                        continue #Führe die For Schleife mit dem nächsten Listenelement fort
                #Versuche den Temperaturwert der Liste hinzuzufügen
                try:
                    sensor1list = np.append(sensor1list,round(float(zeile[1].replace(",",".")),3))
                #Wenn es ein Fehler gab, dann setze die Flag zum markieren, das es ein Fehler gab und füge der Liste einen None Wert hinzu
                except:
                    fehler_flag = True
                    sensor1list = np.append(sensor1list,None)
                #Wenn es sich nicht um ein Differenztemperaturprotokoll handelt, dann weise den Listen die zugehörigen Daten der Sensoren 2-4 zu
                if not differenz_log:
                    #Versuche die Temperaturwerte den Listen hinzuzufügen
                    try:
                        sensor2list = np.append(sensor2list,round(float(zeile[2].replace(",",".")),3))
                    #bei Fehlern setze die Flag und füge der entsprechenden Liste einen None Wert hinzu
                    except:
                        fehler_flag = True
                        sensor2list = np.append(sensor2list,None)
                    try:
                        sensor3list = np.append(sensor3list,round(float(zeile[3].replace(",",".")),3))
                    except:
                        fehler_flag = True
                        sensor3list = np.append(sensor3list,None)
                    try:
                        sensor4list = np.append(sensor4list,round(float(zeile[4].replace(",",".")),3))
                    except:
                        fehler_flag = True
                        sensor4list = np.append(sensor4list,None)
            #Plotte die Daten der ersten Graphlinie und füge diese dem Graphen hinzu
            line1 = ax.plot(datumlist, sensor1list, color='orange',label='Sensor 1')
            ax.add_line(line1[0])
            #Wenn es sich nicht um einen Differenzlog handelt, dann...
            if not differenz_log:
                ax.set_ylabel("Temperatur in °C") #Definiere die Y-Achsen Beschriftung
                #Plotte die anderen Graphenlinien
                line2 = ax.plot(datumlist, sensor2list, color='green',label='Sensor 2')
                line3 = ax.plot(datumlist, sensor3list, color='blue',label='Sensor 3')
                line4 = ax.plot(datumlist, sensor4list, color='red',label='Sensor 4')
                #Füge die Graphlinien dem Graphen hinzu
                ax.add_line(line2[0])
                ax.add_line(line3[0])
                ax.add_line(line4[0])
            #Wenn die Protokolldaten kalibriert sind, dann...
            if kalibriert:
                #Zeige die passende Legende in der Mitte über dem Graphen an
                if differenz_log:
                    ax.legend([line1[0]],["Sensor {} - Sensor {}".format(sen1,sen2)],loc='lower center',bbox_to_anchor=(0.5, 1), ncol=4)
                else:
                    ax.legend([line1[0],line2[0],line3[0],line4[0]],["Sensor 1","Sensor 2","Sensor 3","Sensor 4"],loc='lower center',bbox_to_anchor=(0.5, 1), ncol=4)
            #Wenn die Protokolldaten nicht kalibriert sind, dann...
            else:
                ax.set_title('nicht kalibriert', loc='left',color="red") #Zeige links über dem Graphen den Hinweis nicht kalibriert an
                #Zeige die passende Legende rechts über dem Graphen an
                if differenz_log:
                    ax.legend([line1[0]],["Sensor {} - Sensor {}".format(sen1,sen2)],loc='lower right',bbox_to_anchor=(1, 1), ncol=4)
                else:
                    ax.legend([line1[0],line2[0],line3[0],line4[0]],["Sensor 1","Sensor 2","Sensor 3","Sensor 4"],loc='lower right',bbox_to_anchor=(1, 1), ncol=4)
            
            #Zeichne und platziere den Graphen
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH,expand=True)
            #Toolbar erstellen und platzieren
            toolbar = NavigationToolbar2Tk(canvas, popup_window, pack_toolbar=False)
            toolbar.pack(side=tk.BOTTOM,fill=tk.X)
            #Wenn das Protokoll kein Differenzprotokoll ist, dann...
            if not differenz_log:
                sensoren_anzeigen = [True,True,True,True] #Liste der anzuzeigenden Graphlinien im Graph

                #Funktion zum ein und ausblenden von Graphlinien
                def change_graph(nummer):
                    max_werte = [] #Listen zum Min und Max Werte Bestimmung der anzuzeigenden Graphen
                    min_werte = []
                    sensoren_anzeigen[nummer] = not sensoren_anzeigen[nummer] #Liste der anzuzeigenden Graphlinien ändern
                    #Wenn die Graphlinie angezeigt werden soll, dann...
                    if sensoren_anzeigen[0]:
                        #Max und Min der Graphliniendaten bestimmen
                        max_werte.append(sensor1list[sensor1list != None].max())
                        min_werte.append(sensor1list[sensor1list != None].min())
                        line1[0].set_data(datumlist,sensor1list) #Daten der Graphlinie setzen
                    #Wenn die Graphlinie nicht angezeigt werden soll, dann Daten der Graphlinie zu None Werten ändern
                    else:
                        line1[0].set_data(datumlist,[None])

                    if sensoren_anzeigen[1]:
                        max_werte.append(sensor2list[sensor2list != None].max())
                        min_werte.append(sensor2list[sensor2list != None].min())
                        line2[0].set_data(datumlist,sensor2list)
                    else:
                        line2[0].set_data(datumlist,[None])

                    if sensoren_anzeigen[2]:
                        max_werte.append(sensor3list[sensor3list != None].max())
                        min_werte.append(sensor3list[sensor3list != None].min())
                        line3[0].set_data(datumlist,sensor3list)
                    else:
                        line3[0].set_data(datumlist,[None])

                    if sensoren_anzeigen[3]:
                        max_werte.append(sensor4list[sensor4list != None].max())
                        min_werte.append(sensor4list[sensor4list != None].min())
                        line4[0].set_data(datumlist,sensor4list)
                    else:
                        line4[0].set_data(datumlist,[None])
                    
                    #Wenn die länge der Werte in der Liste für Max Werte größer 0 ist, dann...
                    if len(max_werte)>0:
                        #Min und Max Werte bestimmen
                        max_wert = max(max_werte)
                        min_wert = min(min_werte)
                        abstand = round((max_wert - min_wert)/100*5,2) #Oberen und Unteren Abstand von Graphlinien zum Graphrand berechnen
                        #Wenn der berechnete Abstand 0 ist dann setze diesen auf 1 um die Graphlinie in der Mitte des Graphen anzuzeigen
                        if abstand == 0:abstand = 1
                        ax.set_ylim(ymin=min_wert-abstand,ymax=max_wert+abstand) #Setze die Min und Max Werte der Y-Achse auf die bestimmten Min und Max Werte mit dem berechneten Abstand setzen
                
                    #Stelle den neu gezeichneten Graphen dar
                    canvas.draw()
                #Button erstellen um Graphlinien ein und auszublenden und der Toolbar hinzufügen
                toolbar._Button("Sensor 1",None,None,lambda:change_graph(0))
                toolbar._Button("Sensor 2",None,None,lambda:change_graph(1))
                toolbar._Button("Sensor 3",None,None,lambda:change_graph(2))
                toolbar._Button("Sensor 4",None,None,lambda:change_graph(3))

        #Wenn es ein Fehler beim lesen oder darstellen des Protokolls gab, dann gebe eine Fehlermeldung aus und schließe das Fenster für den Graph
        except Exception:
            messagebox.showerror(parent=popup_window,title = "Fehler beim darstellen", message = "Es trat ein Fehler beim darstellen des Protokolls auf.")
            popup_window.destroy()
            return
        #Wenn es ein Fehler gab dann weise darauf mit einer Meldung hin
        if fehler_flag:
            messagebox.showerror(parent=popup_window,title = "Fehler beim lesen", message = "Es trat ein Fehler beim lesen des Protokolls auf, die Darstellung könnte nicht vollständig sein.")
        #Wenn die Protokolldaten nicht kalibriert sind, dann weise darauf mit einer Meldung hin
        if not kalibriert:
            messagebox.showwarning(parent=popup_window,title = "Nicht kalibriert", message = "Das geladene Protokoll enthält Daten aus einer nicht kalibrierten Messung.")

    #Funktion zum Öffnen eines Pop Up Fensters zum anzeigen des Graphen des Differenzprotokolls
    def show_protokoll_differenz_graph(self,daten,dateiname,sen1,sen2,kalibriert):
        popup_window = Toplevel(self.root) #Pop Up Fenster erzeugen
        popup_window.geometry('1024x680') #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        #x = self.root.winfo_x()
        #y = self.root.winfo_y()
        #popup_window.geometry("+%d+%d" % (x, y)) #Position des Pop Up Fensters festlegen
        popup_window.title(dateiname + " Protokollgraph") #Titel des Pop Up Fensters festlegen

        try:
            fig = plt.figure(figsize=(1,1))
            ax = fig.add_subplot(111) #Es soll nur ein Graph dargestellt werden
            canvas = FigureCanvasTkAgg(fig,popup_window)
            
            ax.autoscale(enable=True, axis="both")
            #Formatiere die X-Achse
            locator = mdates.AutoDateLocator(minticks=8, maxticks=12, interval_multiples=True)
            formatter = mdates.DateFormatter('%Y.%m.%d %H:%M:%S')
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)
            fig.autofmt_xdate(rotation=15,bottom=0.15)
            #Zeige die Achsen an
            ax.axes.get_xaxis().set_visible(True)
            ax.axes.get_yaxis().set_visible(True)
            ax.grid(True) #Zeige das Graphgitter an
            #Definiere die Achsenbeschriftung
            ax.set_xlabel("Messzeitpunkt")
            ax.set_ylabel("Differenztemperatur in °C")

            #Listen für die auszulesenden Daten erstellen
            datumlist = np.array([])
            differenzliste = np.array([])
            
            header = False #Flag zum markieren, dass die nächste Zeile die 2. Headerzeile ist
            fehler_flag = False #Flag zum markieren, dass es min. ein Fehler gab

            #Zeitstempel und berechnete Differenztemperatur den Listen zuweisen
            for zeile in daten:
                #Wenn Zeile die 2. Headerzeile ist, dann...
                if header:
                    header = False #setze die Flag zurück
                    #Versuche...
                    try:
                        datumlist = np.append(datumlist,datumlist[-1]+datetime.timedelta(seconds=1)) #einen Zeitstempel der Liste zuzufügen
                        differenzliste = np.append(differenzliste,None) #Füge der Liste einen None Wert hinzu
                    #Wenn es ein Fehler gab, dann mache nichts
                    except: None
                    continue #Führe die For Schleife mit dem nächsten Listenelement fort
                #Versuche der Liste den Zeitstempel mit dem Format hinzuzufügen
                try:
                    datumlist = np.append(datumlist,datetime.datetime.strptime(zeile[0],"%Y.%m.%d %H:%M:%S"))
                #Wenn es dabei ein Fehler gab, dann...
                except:
                    #Versuche das Format des Zeitstempels zu erkennen
                    try:
                        datumlist = np.append(datumlist,dateutil.parser.parse(zeile[0]))
                    #Wenn es ein Fehler gab, dann...
                    except:
                        #Wenn der Anfang der Zeile Temperaturlogger ist, dann...
                        if zeile[0][0:16] == "Temperaturlogger":
                            header = True #setze die Flag zum markieren das die nächste Zeile die 2. Headerzeile ist
                            continue #Führe die For Schleife mit dem nächsten Listenelement fort
                        fehler_flag = True #Wenn die Zeile mit etwas anderem startet, dann setze die Flag zum markieren, das es ein Fehler gab
                        continue #Führe die For Schleife mit dem nächsten Listenelement fort
                #Versuche den Temperaturwert der Liste hinzuzufügen
                try:
                    differenzliste = np.append(differenzliste,float(zeile[sen1].replace(",",".")) - float(zeile[sen2].replace(",",".")))
                #Wenn es ein Fehler gab, dann setze die Flag zum markieren, das es ein Fehler gab und füge der Liste einen None Wert hinzu
                except:
                    fehler_flag = True
                    differenzliste = np.append(differenzliste,None)

            #Plotte die Daten der ersten Graphlinie und füge diese dem Graphen hinzu
            line1 = ax.plot(datumlist, differenzliste, color='orange',label='Differenztemperatur')
            ax.add_line(line1[0])

            #Wenn die Protokolldaten kalibriert sind, dann...
            if kalibriert:
                ax.legend([line1[0]],["Sensor {} - Sensor {}".format(sen1,sen2)],loc='lower center',bbox_to_anchor=(0.5, 1), ncol=4)
            #Wenn die Protokolldaten nicht kalibriert sind, dann...
            else:
                ax.set_title('nicht kalibriert', loc='left',color="red") #Zeige links über dem Graphen den Hinweis nicht kalibriert an
                #Zeige die passende Legende rechts über dem Graphen an
                ax.legend([line1[0]],["Sensor {} - Sensor {}".format(sen1,sen2)],loc='lower right',bbox_to_anchor=(1, 1), ncol=4)
            
            #Zeichne und platziere den Graphen
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH,expand=True)

            #Toolbar erstellen und platzieren
            toolbar = NavigationToolbar2Tk(canvas, popup_window, pack_toolbar=False)
            toolbar.pack(side=tk.BOTTOM,fill=tk.X)
        #Wenn es ein Fehler beim lesen oder darstellen des Protokolls gab, dann gebe eine Fehlermeldung aus und schließe das Fenster für den Graph
        except:
            messagebox.showerror(parent=popup_window,title = "Fehler beim darstellen", message = "Es trat ein Fehler beim darstellen des Protokolls auf.")
            popup_window.destroy()
            return
        #Wenn es ein Fehler gab dann weise darauf mit einer Meldung hin
        if fehler_flag:
            messagebox.showerror(parent=popup_window,title = "Fehler beim lesen", message = "Es trat ein Fehler beim lesen des Protokolls auf, die Darstellung könnte nicht vollständig sein.")
        #Wenn die Protokolldaten nicht kalibriert sind, dann weise darauf mit einer Meldung hin
        if not kalibriert:
            messagebox.showwarning(parent=popup_window,title = "Nicht kalibriert", message = "Das geladene Protokoll enthält Daten aus einer nicht kalibrierten Messung.")

    #Funktion zum schließen des Fensters
    def close(self):
        self.Templogger.stop_messung() #Rufe die Funktion zum beenden der Messung auf
        #schließe das Fenster
        self.root.destroy()

    #Funktion zum neustarten des Programms
    def restart(self):
        self.Templogger.stop_messung() #Beenden der aktuellen Messung
        #Programm schließen und erneut starten
        os.execv(sys.executable, ['python3'] + sys.argv)

#Klasse zum Erstellen des Graphen
class Graph(tk.Frame):
    #Initialisation des Klassenobjekts
    def __init__(self, parent, Templogger, GUI):
        tk.Frame.__init__(self,parent) #Frame initialisation aufrufen
        self.configure(bg='white') #Framehintergrundfarbe auf Weiß setzen
        self.Templogger = Templogger #Speichern des Objektes für die Messungen
        self.Templogger.Graph = self #Dem Objekt für Messung dieses Objekt mitteilen
        self.GUI = GUI #Dem Objekt für die Darstellung der Bedienoberfläche dieses Objekt mitteilen

        self.ma = None #Maximum der Y-Achse definieren
        self.mi = None #Minimum der Y-Achse definieren
        self.st = None #Abstand des Maximum und Minimums zu den Graphrändern definieren
        
        self.fig = plt.figure(figsize=(1,1)) #Größe des Graph definieren
        self.ax = self.fig.add_subplot(111) #Es soll nur ein Graph dargestellt werden
        
        #self.fig.tight_layout(pad=3.5) #Anpassung der Darstellung des Graphs

        #X-Achse-Werte als Datum festlegen und schräg darstellen
        self.formatter = mdates.DateFormatter('%H:%M:%S')
        self.ax.xaxis.set_major_formatter(self.formatter)
        self.fig.autofmt_xdate(rotation=15,bottom=0.15)

        #Wenn es ein Fehler beim laden der Kalibrierung gab, dann schreibe diesen Hinweis links über den Graphen
        if self.Templogger.kalibrierfehler:
            self.ax.set_title('nicht kalibriert',color="red")

        #Die verschiedenen Graphlinien definieren
        self.line1 = self.ax.plot(self.Templogger.datumlist, self.Templogger.templist1, color='orange')
        self.line2 = self.ax.plot(self.Templogger.datumlist, self.Templogger.templist2, color='green')
        self.line3 = self.ax.plot(self.Templogger.datumlist, self.Templogger.templist3, color='blue')
        self.line4 = self.ax.plot(self.Templogger.datumlist, self.Templogger.templist4, color='red')
        
        #Achsen beschriften
        self.ax.set_xlabel("Messzeitpunkt")
        self.ax.set_ylabel("Temperatur in °C")
        #Achsenbeschriftung beim Start ausblenden
        self.ax.axes.get_xaxis().set_visible(False)
        self.ax.axes.get_yaxis().set_visible(False)

        #Zeichenfläche erstellen und Graph zeichnen
        self.canvas = FigureCanvasTkAgg(self.fig, master = self)
        self.canvas.draw()

        #Dem Graph die Graphlinien zufügen
        self.ax.add_line(self.line1[0])
        self.ax.add_line(self.line2[0])
        self.ax.add_line(self.line3[0])
        self.ax.add_line(self.line4[0])
        
        self.ax.grid(True) #Graphgitter aktivieren
        #Graph platzieren
        self.canvas.get_tk_widget().pack(fill="both",expand=True)

    #Funktion zum akuallisieren des Graphen
    def update(self,sensoren_anzeigen,sen1,sen2):
        #Wenn ein Differenztemperaturgrap dargestellt werden soll, dann...
        if sen2 != None:
            #Ändere die Y-Achsen Beschriftung
            self.ax.set_ylabel("Differenztemperatur in °C")
            #Wenn es einen Fehler beim laden der Kalibrierung gab, dann...   
            if self.Templogger.kalibrierfehler:
                #setze die Legende rechts über den Graph
                self.ax.legend([self.line1[0],self.line2[0],self.line3[0],self.line4[0]],["Sensor {} - Sensor {}".format(sen1,sen2)],loc='lower right',bbox_to_anchor=(1, 1), ncol=4)
            #Wenn nicht, dann...
            else:
                #setze die Legende mittig über den Graph
                self.ax.legend([self.line1[0],self.line2[0],self.line3[0],self.line4[0]],["Sensor {} - Sensor {}".format(sen1,sen2)],loc='lower center',bbox_to_anchor=(0.5, 1), ncol=4)
            #Wenn die Temperaurliste ein oder mehrere None Werte enthält, dann...
            if None in self.Templogger.templist1:
                teilliste = self.Templogger.templist1[self.Templogger.templist1 != None] #Filtere die None Werte raus und speicher dies in einer temporären Liste
                #Bestimme Maximum und Minimum der Teilliste
                self.ma = teilliste.max()
                self.mi = teilliste.min()
            #Wenn die Temperaturliste keine None Werte enthält, dann...
            else:
                #Bestimme Maximum und Minimum der Temperaturliste
                self.ma = self.Templogger.templist1.max()
                self.mi = self.Templogger.templist1.min()
            #Bestimme den Abstand des Maximum und Minimumpunkt zur Graphbegrenzung
            self.st = round((self.ma - self.mi) / 100 * 5, 3)
            #Wenn der Abstand 0 ist dann setze den Abstand auf 1
            if self.st == 0: self.st = 1
            #Runde die Maximum und Minimum Werte auf 2 Nachkommastellen
            self.ma = round(self.ma,3)
            self.mi = round(self.mi,3)
            self.ax.set_ylim(ymax=self.ma+self.st, ymin=self.mi-self.st) #Setzte das Maximum und Minimum der Y-Achse auf die ermittelten Werte
            y_achse_werte = np.unique(np.around(np.linspace(self.mi, self.ma, 10),2)) #Bestimmt die Werte welche in der Y-Achsen Beschriftung stehen sollen
            #Wenn die Liste für die Y-Achsen Werte nur 1 Wert enthält, dann setzte die Y-Achsen Min und Max Werte auf +-1 des Graphlinienwerts, so wird die Graphlinie in der Mitte des Graphen angezeigt
            if len(y_achse_werte) == 1:
                y_achse_werte = np.unique(np.around(np.linspace(self.mi-1, self.ma+1, 10),2))
            self.ax.set_yticks(y_achse_werte) #Ermittel die Zahlen für die Y-Achse um 10 Werte in der Y-Achse darzustellen
        #Wenn es eine Echtzeittemperaturgraph dargestellt werden soll, dann....
        else:
            #Ändere die Y-Achsen Beschriftung
            self.ax.set_ylabel("Temperatur in °C")
            #Erstelle Listen um die Legende zu bestimmen
            legenden_text = []
            legende_linien = []
            #Schleife um zu bestimmen welche Sensoren dargestellt werden sollen und zum erstellen der Legende
            for nummer,sensor in enumerate(sensoren_anzeigen):
                #Wenn der Sensor angezeigt werden soll, dann...
                if sensor:
                    legenden_text.append("Sensor {}".format(nummer+1)) #Füge den Text zu Liste hinzu
                    legende_linien.append([self.line1[0],self.line2[0],self.line3[0],self.line4[0]][nummer]) #Füge die linie der Liste hinzu
            #Wenn es ein Fehler beim laden der Kalibrierung gab, dann zeige die Legende mit dem ermittelten Text für die ermittelten Linien rechts über den Graph
            if self.Templogger.kalibrierfehler:
                self.ax.legend(legende_linien,legenden_text,loc='lower right',bbox_to_anchor=(1, 1), ncol=4)
            #Wenn es kein Fehler gab, dann zeige die Legende mit dem ermittelten Text für die ermittelten Linien mittig über den Graph
            else:
                self.ax.legend(legende_linien,legenden_text,loc='lower center',bbox_to_anchor=(0.5, 1), ncol=4)
        
            #Wenn ein Sensor dargestellt werden soll, dann...
            if 1 in sensoren_anzeigen:
                #Wenn die Temperaurliste1 ein oder mehrere None Werte enthält, dann...
                if None in self.Templogger.templist1[-self.Templogger.zeitraum_eintraege:]:
                    max_werte_liste = []
                    min_werte_liste = []
                    #Wenn der Sensor dargestellt werden soll, dann...
                    if sensoren_anzeigen[0]:
                        #Filtere die None Werte raus und speicher dies in einer temporären Liste
                        teilliste = self.Templogger.templist1[-self.Templogger.zeitraum_eintraege:][self.Templogger.templist1[-self.Templogger.zeitraum_eintraege:] != None]
                        #Bestimme Maximum und Minimum der Teilliste
                        max_werte_liste.append(teilliste.max())
                        min_werte_liste.append(teilliste.min())
                    if sensoren_anzeigen[1]:
                        teilliste = self.Templogger.templist2[-self.Templogger.zeitraum_eintraege:][self.Templogger.templist2[-self.Templogger.zeitraum_eintraege:] != None]
                        max_werte_liste.append(teilliste.max())
                        min_werte_liste.append(teilliste.min())
                    if sensoren_anzeigen[2]:
                        teilliste = self.Templogger.templist3[-self.Templogger.zeitraum_eintraege:][self.Templogger.templist3[-self.Templogger.zeitraum_eintraege:] != None]
                        max_werte_liste.append(teilliste.max())
                        min_werte_liste.append(teilliste.min())
                    if sensoren_anzeigen[3]:
                        teilliste = self.Templogger.templist4[-self.Templogger.zeitraum_eintraege:][self.Templogger.templist4[-self.Templogger.zeitraum_eintraege:] != None]
                        max_werte_liste.append(teilliste.max())
                        min_werte_liste.append(teilliste.min())
                    if len(max_werte_liste) != 0:
                        self.ma = max(max_werte_liste)
                        self.mi = min(min_werte_liste)
                #Wenn die Temperaturliste1 keine None Werte enthält, dann...
                else:
                    max_werte_liste = []
                    min_werte_liste = []
                    #Wenn der Sensor angezeigt werden soll, dann...
                    if sensoren_anzeigen[0]:
                        #Bestimme Maximum und Minimum der entsprechenden Temperaturliste
                        max_werte_liste.append(self.Templogger.templist1[-self.Templogger.zeitraum_eintraege:].max())
                        min_werte_liste.append(self.Templogger.templist1[-self.Templogger.zeitraum_eintraege:].min())
                    if sensoren_anzeigen[1]:
                        max_werte_liste.append(self.Templogger.templist2[-self.Templogger.zeitraum_eintraege:].max())
                        min_werte_liste.append(self.Templogger.templist2[-self.Templogger.zeitraum_eintraege:].min())
                    if sensoren_anzeigen[2]:
                        max_werte_liste.append(self.Templogger.templist3[-self.Templogger.zeitraum_eintraege:].max())
                        min_werte_liste.append(self.Templogger.templist3[-self.Templogger.zeitraum_eintraege:].min())
                    if sensoren_anzeigen[3]:
                        max_werte_liste.append(self.Templogger.templist4[-self.Templogger.zeitraum_eintraege:].max())
                        min_werte_liste.append(self.Templogger.templist4[-self.Templogger.zeitraum_eintraege:].min())
                    if len(max_werte_liste) != 0:
                        self.ma = max(max_werte_liste)
                        self.mi = min(min_werte_liste)
                #Bestimme den Abstand des Maximum und Minimumpunkt zur Graphbegrenzung
                self.st = round((self.ma - self.mi) / 100 * 5, 3)
                #Wenn der Abstand 0 ist dann setze den Abstand auf 1
                if self.st == 0: self.st = 1
                #Runde die Maximum und Minimum Werte auf 2 Nachkommastellen
                self.ma = round(self.ma,2)
                self.mi = round(self.mi,2)
                self.ax.set_ylim(ymax=self.ma+self.st, ymin=self.mi-self.st) #Setzte das Maximum und Minimum der Y-Achse auf die ermittelten Werte
                y_achse_werte = np.unique(np.around(np.linspace(self.mi, self.ma, 10),2)) #Bestimmt die Werte welche in der Y-Achsen Beschriftung stehen sollen
                #Wenn die Liste für die Y-Achsen Werte nur 1 Wert enthält, dann setzte die Y-Achsen Min und Max Werte auf +-1 des Graphlinienwerts, so wird die Graphlinie in der Mitte des Graphen angezeigt
                if len(y_achse_werte) == 1:
                    y_achse_werte = np.unique(np.around(np.linspace(self.mi-1, self.ma+1, 10),2))
                self.ax.set_yticks(y_achse_werte) #Ermittel die Zahlen für die Y-Achse um 10 Werte in der Y-Achse darzustellen
            #Wenn kein Sensor dargestellt werden soll, dann...
            else:
                #Wenn noch kein Maximum ermittelt wurde setze die Y-Achse auf Maxmium 1 und Minimum 0
                if self.ma == None:
                    self.ax.set_ylim(ymax=1, ymin=0)
                    
        #Wenn der Sensor dargestellt werden soll, dann...
        if sensoren_anzeigen[0]:
            self.line1[0].set_data(self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege:],self.Templogger.templist1[-self.Templogger.zeitraum_eintraege:]) #Aktuallisiere die Daten der Graphlinie
        else:
            self.line1[0].set_data(self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege:],[None]*self.Templogger.zeitraum_eintraege)
        
        if sensoren_anzeigen[1]:
            self.line2[0].set_data(self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege:],self.Templogger.templist2[-self.Templogger.zeitraum_eintraege:])
        else:
            self.line2[0].set_data(self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege:],[None]*self.Templogger.zeitraum_eintraege)

        if sensoren_anzeigen[2]:
            self.line3[0].set_data(self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege:],self.Templogger.templist3[-self.Templogger.zeitraum_eintraege:])
        else:
            self.line3[0].set_data(self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege:],[None]*self.Templogger.zeitraum_eintraege)

        if sensoren_anzeigen[3]:
            self.line4[0].set_data(self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege:],self.Templogger.templist4[-self.Templogger.zeitraum_eintraege:])
        else:
            self.line4[0].set_data(self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege:],[None]*self.Templogger.zeitraum_eintraege)
        
        self.ax.set_xlim(left=self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege], right=self.Templogger.datumlist[-1]) #Setze den linken Wert der X-Achse auf den ältesten Wert der Zeitstempel und den rechten Wert auf den neusten Zeitstempel
        steps_xticks = int(self.Templogger.zeitraum_eintraege / 11) #Ermittel die Schrittzahl um die entsprechenden Zeitstempel der X-Achsenbeschriftung hinzuzufügen und um 11 Zeitstempel darzustellen
        if steps_xticks == 0: steps_xticks = 1
        self.ax.set_xticks(self.Templogger.datumlist[-self.Templogger.zeitraum_eintraege::steps_xticks]) #Setze die X-Achsenbeschriftung auf die ermittelten Zeitstempel
        
        self.ax.set_title('')
        self.ax.set_title('', loc='left')

        if self.Templogger.kalibrierfehler:
            self.ax.set_title('nicht kalibriert', loc='left',color="red")

        #Lass die Achsenbeschriftungen anzeigen
        self.ax.axes.get_xaxis().set_visible(True)
        self.ax.axes.get_yaxis().set_visible(True)

        #Wenn der Thread für die Darstellung beendet werden soll, dann verlasse die Funktion
        if self.Templogger.stop_all_threads.is_set(): return
        #Stelle den neu gezeichneten Graphen dar
        self.canvas.draw()

#Wenn diese Datei als Programm aufgerufen und nicht als Modul importiert wird, dann...
if __name__ == "__main__":
    DEBUG = False #Deaktiviert den Debug Betriebsmodus
    #DEBUG = True #nur für die Entwicklungszeit, danach entfernen
    #Wenn das Programm mit dem Argument DEBUG aufgerufen wird, dann...
    if "DEBUG" in sys.argv[1:]:
        DEBUG = True #Aktiviere den Debug Betriebsmodus
    #Erstelle das Klassenobjekt um die Bedienoberfläche darzustellen
    GUI()
    input("Druecken Sie Enter zum schließen der Konsole.")