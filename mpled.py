#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Ein kleines Tool zur Anzeige von Festplatten- bzw. MountPoint-Aktivität
# D.Ahlgrimm
# 23.11.2012: terminal-ausgabe
# 24.11.2012: wx-fenster-ausgabe
# 25.11.2012: erweiterung, um auch mit lvm umgehen zu können
# 27.11.2012: swap mit aufgenommen
# 30.08.2015: Korrektur bei der Fenstergröße für wxWidgets v3

import wx
import time
import os

FIX_CORNER=3          # 0=upper-left, 1=upper-right, 2=lower-left, 3=lower-right
FONT_SIZE=10          # any Fontsize (~ 8 - 20)
INCLUDE_SWAP=False    # auf True, wenn die SWAP-Partition angezeigt werden soll
FRAME_NO_TASKBAR=True # auf True, wenn das Fenster nicht in der Taskbar erscheinen soll

# ###########################################################
# Mappt Device-Namen auf Mount-Points.
#
# Erwartet folgende Dateien:
#   /proc/swaps
#   /proc/mounts
# und ggf. für LVM
#   /sys/block/dm-?/dm/name
#
# Der Aufruf:
#   a=Mount_zu_dev()
#   print a.getData()
# liefert z.B. folgendes Dictionary:
#   {'sdg4': '/', 'sde1': '/1.5TB', 'sdf1': '/1TB', 'sdd5': '/windows/D_Daten', 'sdc1': '/300GB', 'sdb1': '/2TB'}
class Mount_zu_dev():
  def __init__(self):
    bdr={}
    self.rel={}

    bd=os.listdir("/sys/block/")  # Sonderbehandlung für LVM
    for i in bd:
      if i[:3]=="dm-":
        fl=open("/sys/block/"+i+"/dm/name", "r")
        bdr.update({fl.readline().strip():i})
        fl.close()
    # liefert z.B.: bdr={'system-home': 'dm-0', 'system-swap': 'dm-2', 'system-root': 'dm-1'}

    if INCLUDE_SWAP==True:
      fl=open("/proc/swaps", "r") # Swap-Partitionen
      for ln in fl:
        ln=ln.strip()
        if ln[:5]=="/dev/":
          lns=ln.split()
          self.rel.update({lns[0][5:]:"swap("+lns[0][5:]+")"})
      fl.close()

    fl=open("/proc/mounts", "r")
    for ln in fl:
      ln=ln.strip()
      if ln[:5]=="/dev/":
        lns=ln.split()
        if ln[:12]=="/dev/mapper/":
          self.rel.update({bdr[lns[0][12:]]:lns[1].replace("\\040", " ")})
        elif ln[:18]=="/dev/disk/by-uuid/":
          rp=os.path.realpath(lns[0])
          if rp[:5]=="/dev/":
            self.rel.update({rp[5:]:lns[1].replace("\\040", " ")})
        else:
          self.rel.update({lns[0][5:]:lns[1].replace("\\040", " ")})
    fl.close()

  def getData(self):
    return(self.rel)



# ###########################################################
# Für /proc/diskstats wird folgender Aufbau angenommen:
#data> 8     100 sdg4 85567 43938 5297050 1731308 215575 45803 9433864 27720295 0 906883 29451437
#idx > 0      1   2    3     4     5       6       7      8     9       10      11 12     13
# Die Felder enthalten:
# 03 -- # of reads issued
# 04 -- # of reads merged
# 05 -- # of sectors read
# 06 -- # of milliseconds spent reading
# 07 -- # of writes completed
# 08 -- # of writes merged
# 09 -- # of sectors written
# 10 -- # of milliseconds spent writing
# 11 -- # of I/Os currently in progress
# 12 -- # of milliseconds spent doing I/Os
# 13 -- weighted # of milliseconds spent doing I/Os#
#
# Liefert via getData() z.B.:
# {'sdg4': [7065682L, 27981224L], ....,  'sdc1': [2234170L, 2044960L], 'sdb1': [22508466L, 7525608L]}
# wobei der erste Parameter bzw. Key jew. der Devicename ist,
# der zweite die "sectors read" und
# der dritte die "sectors written"
#
# Liefert via getMzd() den Output von Mount_zu_dev.getData()
class diskstats():
  def __init__(self):
    self.dic={}
    self.hist={}
    mzd=Mount_zu_dev()
    self.mzd=mzd.getData()  # devicename-mountpoint-relation laden

  def getData(self):
    fl=open("/proc/diskstats", "r")
    for ln in fl:
      ln=ln.strip().split()
      if ln[2] in self.mzd: # wenn devicename in der devicename-mountpoint-relation gefunden wird...
        self.dic.update({ln[2]:[long(ln[5]), long(ln[9])]}) # ...in outputlist merken
    fl.close()
    return(self.dic)

  def getMzd(self):
    return(self.mzd)

  def printData(self):  # für Tests
    print
    for i in self.mzd:  # Reihenfolge aus /proc/mounts
      print "{0:20}".format(self.mzd[i]), i, \
            "{0:10}".format(self.dic[i][0]-self.hist[i][0]), "{0:10}".format(self.dic[i][1]-self.hist[i][1]), \
            "{0:15}".format(self.dic[i][0]), "{0:15}".format(self.dic[i][1])

  def dauerlauf(self):  # für Tests
    self.getData()
    while True:
      for i in self.dic:
        self.hist.update({i:[self.dic[i][0], self.dic[i][1]]})
      time.sleep(1)
      self.getData()
      self.printData()
      
      

# ###########################################################
# Das Fenster.
class MPLED2Panel(wx.Window):
  def __init__(self, parent):
    wx.Window.__init__(self, parent)

    self.load_diskstats()
    self.d=self.h=self.ds.getData()

    self.parent=parent
    self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
    self.fnt=wx.Font(FONT_SIZE, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
    self.Bind(wx.EVT_PAINT, self.on_paint)

    self.MenueErstellen()
    self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)

    self.Bind(wx.EVT_TIMER, self.on_timer)
    self.timer=wx.Timer(self)
    self.updateIntervall=100  # 10 mal pro Sekunde sollte langen
    self.timer.Start(self.updateIntervall)

    self.farbeHintergrund="#CCCCCC"
    self.farbeSchrift="#000000"
    self.dc=None

  # ###########################################################
  # Stellt das Kontext-Menue dar.
  def OnContextMenu(self, event):
    self.PopupMenu(self.menue)

  # ###########################################################
  # Legt das Kontext-Menue an.
  def MenueErstellen(self):
    self.menue=wx.Menu()
    self.menue.Append(100, 'Save position')
    self.Bind(wx.EVT_MENU, self.PositionSchreiben, id=100)

  # ###########################################################
  # Speichert die Position des Fensters im Konfig-File.
  def PositionSchreiben(self, event):
    fc=wx.FileConfig(localFilename=".mpled.rc")
    sp=self.parent.GetScreenPosition()
    ss=self.parent.GetSizeTuple()

    fc.WriteInt("pos_x",  sp[0])
    fc.WriteInt("pos_y",  sp[1])
    fc.WriteInt("size_x", ss[0])
    fc.WriteInt("size_y", ss[1])
    fc.Flush()

  # ###########################################################
  # Ruft einmal pro Update-Intervall die Anzeige-Update-Funktion
  # auf.
  def on_timer(self, event):
    self.update_drawing()

  # ###########################################################
  # Aktualisiert die internen Listen pro Update-Intervall, um
  # danach einen Fenster-Refresh einzuleiten, bei dem die
  # Updates an den Listen dargestellt werden.
  def update_drawing(self):
    if self.dscnt>=10:
      self.load_diskstats() # jedes 10te Mal neu, um Änderungen an den Mountpoints zu erkennen
    else:
      self.dscnt+=1
    self.h=self.d.copy() # alte Werte = neue Werte
    self.d=self.ds.getData()
    self.Refresh(False)

  # ###########################################################
  # Lädt die diskstats-Klasse [neu], um dabei ggf. geänderte
  # Mountpoints zu erkennen und erzeugt eine sortierte Liste
  # mit den Mountpoints für die Anzeige-Reihenfolge.
  def load_diskstats(self):
    self.ds=diskstats()
    self.dscnt=0
    self.mzd=self.ds.getMzd()

    self.sl=[]
    for i in self.mzd:  # zum Sortieren nach Mountpoint -> als Liste umwandeln
      self.sl.append((self.mzd[i], i))
    self.sl.sort()

  # ###########################################################
  # Aktualisiert das Fenster.
  def on_paint(self, event):
    self.dc=wx.AutoBufferedPaintDC(self)
    self.dc.SetBackground(wx.Brush(self.farbeHintergrund))
    self.dc.Clear()

    self.dc.SetTextForeground(self.farbeSchrift)
    self.dc.SetFont(self.fnt)
    w, h=self.dc.GetTextExtent("_")     # Abmessungen eines Buchstaben
    sa=4                                # Abstand zwischen Spalten
    led_radius=max(4, (h-sa)//2)        # Radius einer LED
    brdrh=5                             # Rand horizontal
    brdrv=3                             # Rand vertikal
    led_wth=2*led_radius+sa             # Breite einer LED-Spalte

    self.dc.DrawText("R", brdrh, brdrv)  # "Überschrift" ausgeben
    self.dc.DrawText("W", brdrh+led_wth, brdrv)

    z=1
    for mp, dv in self.sl: # über alle (sortierten) Mountpoints
      if dv not in self.h or dv not in self.d:
        continue

      wa, ha=self.dc.GetTextExtent(mp)
      w=max(w, wa)  # der längste Mountpoint-Text bestimmt, wie breit das Fenster wird
      y=brdrv+z*h

      if self.d[dv][0]!=self.h[dv][0]:  # wenn Read-Wert sich geändert hat...
        self.dc.SetBrush(wx.Brush("YELLOW"))  # LED anschalten
      else:
        self.dc.SetBrush(wx.Brush(self.farbeHintergrund)) # sonst aus
      self.dc.DrawCirclePoint((brdrh+led_radius, y+h//2), led_radius) # LED darstellen

      if self.d[dv][1]!=self.h[dv][1]:  # wenn Write-Wert sich geändert hat...
        self.dc.SetBrush(wx.Brush("RED"))
      else:
        self.dc.SetBrush(wx.Brush(self.farbeHintergrund))
      self.dc.DrawCirclePoint((brdrh+led_radius+led_wth, y+h//2), led_radius)

      self.dc.DrawText(mp, brdrh+2*led_wth+sa, y) # Mountpoint anzeigen
      z+=1

    sp=self.parent.GetScreenPosition()        # Bildschirm-Position des Fensters (oben-links)
    #ss=self.parent.GetSizeTuple()             # aktuelle Fenster-Abmessungen
    #ssn=(2*brdrh+2*led_wth+sa+w, h*z+2*brdrv) # neue geforderte Fenster-Abmessungen
    ss=self.parent.GetSize()             # aktuelle Fenster-Abmessungen
    ssc=self.parent.GetSize()-self.parent.GetClientSize() # Korrektur-Werte für wxWidgets3
    ssn=(2*brdrh+2*led_wth+sa+w+ssc[0], h*z+2*brdrv+ssc[1]) # neue geforderte Fenster-Abmessungen
    if ss!=ssn: # wenn sich die Größe geändert hat...
      dwh=(ssn[0]-ss[0], ssn[1]-ss[1])  # Delta-Werte
      if FIX_CORNER==0:   # upper-left
        spn=sp
      elif FIX_CORNER==1: # upper-right
        spn=(sp[0]-dwh[0], sp[1])
      elif FIX_CORNER==2: # lower-left
        spn=(sp[0], sp[1]-dwh[1])
      elif FIX_CORNER==3: # lower-right
        spn=(sp[0]-dwh[0], sp[1]-dwh[1])
      else:
        print "Error: illegal value for FIX_CORNER"
      self.parent.Move(spn)
      self.parent.SetSize(ssn) # neue Größe einstellen
      wx.Yield()
      # noch etwas warten, damit die Änderung beim nächsten Durchlauf
      # dann auch fertig ist...und "sp" und "ss" die neuen Werte bekommen.
      wx.MilliSleep(100)



# ###########################################################
# Der Fenster-Rahmen fuer das Hauptfenster.
class MPLED2Frame(wx.Frame):
  def __init__(self, parent, pos=wx.DefaultPosition, size=wx.DefaultSize):
    style=wx.DEFAULT_FRAME_STYLE
    if FRAME_NO_TASKBAR==True:
      style|=wx.FRAME_NO_TASKBAR
    wx.Frame.__init__(self, None, wx.ID_ANY, "MPLED v1.0", pos=pos, size=size, style=style)
    self.panel=MPLED2Panel(self)


# ###########################################################
# Der Starter
if __name__=='__main__':
  fc=wx.FileConfig(localFilename=".mpled.rc")
  spx=fc.ReadInt("pos_x", -1)
  spy=fc.ReadInt("pos_y", -1)
  ssx=fc.ReadInt("size_x", -1)
  ssy=fc.ReadInt("size_y", -1)

  app=wx.App(False)
  frame=MPLED2Frame(None, pos=(spx, spy), size=(ssx, ssy))
  frame.Show(True)
  app.MainLoop()

#a=diskstats()
#a.dauerlauf()

#b=Mount_zu_dev()
#print b.getData()


