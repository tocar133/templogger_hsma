#!/usr/bin/python3
# -*- coding: iso-8859-1 -*-

from tkinter import Toplevel, messagebox
import tkinter as tk
import csv

#Klasse zum bestimmen der Kalibrierungswerte
class Kalibrierung():
    #Initialisation des Klassenobjekts
    def __init__(self,GUI):
        self.GUI = GUI
        self.Templogger = None
        self.temps0 = None
        self.temps100 = None

    #Funktion zum prüfen des eingegebenen Werts und zum fortführen des Kalibrierungsprozesses
    def eingabe_testen(self,popup_window,temp_ref):
        #Wenn der eingegebene Wert ein Komme enthält, dann soll dieser durch ein Punkt ersetzt werden
        if "," in temp_ref:
            temp_ref = temp_ref.replace(",",".")
        #Versuche die Eingabe zu einer float Zahl zu konvertieren
        try:
            temp_ref = float(temp_ref)
            temp_ref = round(temp_ref,3)
        #Wenn das Konvertieren fehlgeschlagen ist, dann öffne ein Fenster mit einer Fehlermeldung und kehre zum eingabe Fenster zurück
        except:
            messagebox.showerror(parent=popup_window,title = "Fehlerhafte Eingabe", message = "Bitte geben Sie eine Zahl ein.")
            return
        #Wenn die ersten Kalibrierungswerte noch nicht vonhanden sind, dann...
        if self.temps0 == None:
            popup_window.destroy() #Schließe das Eingabefenster

            temp1 = round(self.Templogger.sensor1.temperature,3)
            temp2 = round(self.Templogger.sensor2.temperature,3)
            temp3 = round(self.Templogger.sensor3.temperature,3)
            temp4 = round(self.Templogger.sensor4.temperature,3)

            self.temps0 = [temp_ref,temp1,temp2,temp3,temp4] #Speichere die Daten zwischen
            self.kalibrieren_100_popup() #Rufe das Fenster zur 100 Grad Kalibrierung auf
        #Wenn die zweiten Kalibrierungswerte noch nicht vonhanden sind, dann...
        elif self.temps100 == None:
            popup_window.destroy() #Schließe das Eingabefenster

            temp1 = round(self.Templogger.sensor1.temperature,3)
            temp2 = round(self.Templogger.sensor2.temperature,3)
            temp3 = round(self.Templogger.sensor3.temperature,3)
            temp4 = round(self.Templogger.sensor4.temperature,3)

            self.temps100 = [temp_ref,temp1,temp2,temp3,temp4] #Speichere die Daten zwischen
            #Rufe die Funktion zur Speicherung der Daten in die Kalibrierungsdatei auf
            self.kalibrierung_speichern()

    #Funktion zum starten der Kalibrierung
    def start_kalibrieren(self):
        #Wenn momentan eine Messung läuft, dann...
        if not self.GUI.check_stop():
            return False
        #if self.Templogger.messung_gestartet:
        #    antwort = messagebox.askyesno(title="Messung beenden?", message="Wollen Sie die aktuelle Messung beenden?") #Öffne ein Fenster und frage ob die aktuelle Messung beendent werden soll
        #    #Wenn die Messung beendet werden soll, dann beende die Messung, wenn nicht dann verlasse die Funktion
        #    if antwort:
        #        self.Templogger.stop_messung()
        #    else:
        #        return False
        #Setze die Kalibrierungswerte des Klassenobjekts zurück
        self.temps0 = None
        self.temps100 = None
        #Rufe das Fenster für die 0 Grad Kalibrierung auf
        self.kalibrieren_0_popup()

    #Funktion zum erstellen des Fensters zur 0 Grad Kalibrierungs
    def kalibrieren_0_popup(self):
        popup_window = Toplevel(self.GUI.root) #Pop Up Fenster erzeugen
        popup_window.geometry("370x150") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.GUI.root.winfo_x()
        y = self.GUI.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.GUI.root.winfo_width()-370)/2, y + (self.GUI.root.winfo_height()-150)/2)) #Position des Pop Up Fensters festlegen
        popup_window.wm_transient(self.GUI.root)
        popup_window.title("Kalibrieren für 0 °C") #Titel des Pop Up Fensters festlegen

        #Label für die Beschriftung erstellen und platzieren
        beschreibungs_label = tk.Label(popup_window,font=self.GUI.font, text="Referenztemperatur [°C]:", pady=10)
        beschreibungs_label.pack()
        #Eingabefeld für die Referenztemperatur erstellen und platzieren
        referenz_temp = tk.Entry(popup_window,font=self.GUI.font, width=30, bg="light yellow")
        referenz_temp.pack(ipady=7)

        #Funktion zum aufrufen der Funktion um die Eingabe zu prüfen
        def aufruf_zum_testen():
            self.eingabe_testen(popup_window,referenz_temp.get())

        #Buttons zum Bestätigen oder Abbrechen der Eingabe erstellen und platzieren
        button_frame = tk.Frame(popup_window,pady=5)
        button_frame.pack()
        okbutton = tk.Button(button_frame,font=self.GUI.font, text="0 °C kalibrieren", command=aufruf_zum_testen,height=2,width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame,font=self.GUI.font, text="Abbrechen", command=lambda: self.kalibrierung_abbrechen(popup_window), height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)

        #Beim Enter drücken die Funktion zum Prüfen der Eingabeparameter aufrufen
        referenz_temp.bind("<Return>", lambda _: aufruf_zum_testen())

        #Beim anklicken des Elements, die Bildschirmtastatur öffnen
        referenz_temp.bind("<Button-1>",lambda _: self.GUI.open_keyboard())

        #Beim Escape drücken das Fenster schließen
        popup_window.bind("<Escape>", lambda _: self.kalibrierung_abbrechen(popup_window))

    #Funktion zum erstellen des Fensters zur 100 Grad Kalibrierungs
    def kalibrieren_100_popup(self):
        popup_window = Toplevel(self.GUI.root) #Pop Up Fenster erzeugen
        popup_window.geometry("370x150") #Größe des Pop Up Fensters festlegen
        #Positions des Hauptfensters abfragen
        x = self.GUI.root.winfo_x()
        y = self.GUI.root.winfo_y()
        popup_window.geometry("+%d+%d" % (x + (self.GUI.root.winfo_width()-370)/2, y + (self.GUI.root.winfo_height()-150)/2)) #Position des Pop Up Fensters festlegen
        popup_window.wm_transient(self.GUI.root)
        popup_window.title("Kalibrieren für 100 °C") #Titel des Pop Up Fensters festlegen

        #Label für die Beschriftung erstellen und platzieren
        beschreibungs_label = tk.Label(popup_window,font=self.GUI.font, text="Referenztemperatur [°C]:", pady=10)
        beschreibungs_label.pack()
        #Eingabefeld für die Referenztemperatur erstellen und platzieren
        referenz_temp = tk.Entry(popup_window,font=self.GUI.font, width=30, bg="light yellow")
        referenz_temp.pack(ipady=7)
        
        #Funktion zum aufrufen der Funktion um die Eingabe zu prüfen
        def aufruf_zum_testen():
            self.eingabe_testen(popup_window,referenz_temp.get())

        #Buttons zum Bestätigen oder Abbrechen der Eingabe erstellen und platzieren
        button_frame = tk.Frame(popup_window,pady=5)
        button_frame.pack()
        okbutton = tk.Button(button_frame,font=self.GUI.font, text="100 °C kalibrieren", command=aufruf_zum_testen,height=2,width=15)
        okbutton.pack(side=tk.LEFT)
        cancelbutton = tk.Button(button_frame,font=self.GUI.font, text="Abbrechen", command=lambda: self.kalibrierung_abbrechen(popup_window), height=2, width=15)
        cancelbutton.pack(side=tk.LEFT)

        #Beim Enter drücken die Funktion zum Prüfen der Eingabeparameter aufrufen
        referenz_temp.bind("<Return>", lambda _: aufruf_zum_testen())

        #Beim anklicken des Elements, die Bildschirmtastatur öffnen
        referenz_temp.bind("<Button-1>",lambda _: self.GUI.open_keyboard())

        #Beim Escape drücken das Fenster schließen
        popup_window.bind("<Escape>", lambda _: self.kalibrierung_abbrechen(popup_window))

    #Funktion zur Speicherung der ermittelten Kalibrierungswerte
    def kalibrierung_speichern(self):
        #Versuche...
        try:
            #Bei den ermittelten Kalibrierungswerte die Punkte durch Kommas ersetzen
            temps0 = [str(wert).replace(".",",") for wert in self.temps0]
            temps100 = [str(wert).replace(".",",") for wert in self.temps100]
            #Erstelle oder Ersetze die Datei und öffne diese zum schreiben
            with open(self.Templogger.programm_pfad + "/kalibrierung.csv","w") as datei:
                #Schreibe die Kalibrierungswerte in die Datei
                schreiber = csv.writer(datei,delimiter=';')
                schreiber.writerow(temps0)
                schreiber.writerow(temps100)
            #Öffne ein Fenster mit der Meldung, dass die Kalibrierungs abgeschlossen ist
            messagebox.showinfo(parent=self.GUI.root,title="Kalibrierung abgeschlossen", message="Die Kalibrierung ist abgeschlossen und wurde gespeichert.")
        #Wenn ein Fehler auftrat, dann öffne ein Fenster mit der Meldung, dass es fehlgeschlagen ist
        except:
            messagebox.showinfo(parent=self.GUI.root,title="Kalibrierung fehlgeschlagen", message="Die Kalibrierung ist fehlgeschlagen.")

    #Funktion zum abbrechen des Kalibrierungsprozesses
    def kalibrierung_abbrechen(self,popup_window):
        #Öffne ein Fenster und frage ob der Kalibrierungsprozess abgebrochen werden soll
        antwort = messagebox.askyesno(title="Kalibrierung abbrechen?", message="Wollen Sie die Kalibrierung wirklich abbrechen?") #Öffne ein Fenster und frage ob die Protokolldatei trotzdem geladen werden soll
        #Wenn der Kalibrierungsprozess beendet werden soll, dann beende schließe das Eingabefenster
        if antwort:
            popup_window.destroy()