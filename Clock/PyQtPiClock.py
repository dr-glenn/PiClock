# -*- coding: utf-8 -*-                 # NOQA

import sys
import os
import platform
import signal
import datetime
import time
import json
import locale
import random
import re
import logging
from logging.handlers import RotatingFileHandler,TimedRotatingFileHandler
#logging.basicConfig(filename='piclock.log', level=logging.WARNING)
#handler = RotatingFileHandler('piclock.log', maxBytes=50000, backupCount=3)
handler = TimedRotatingFileHandler('piclock.log', when='midnight', interval=1, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s : %(message)s')
handler.setFormatter(formatter)
defLogger = logging.getLogger('')
defLogger.addHandler(handler)
defLogger.setLevel(logging.DEBUG)
logger = logging.getLogger('piclock')

from PyQt4 import QtGui, QtCore, QtNetwork
from PyQt4.QtGui import QPixmap, QMovie, QBrush, QColor, QPainter
from PyQt4.QtCore import QUrl
from PyQt4.QtCore import Qt
from PyQt4.QtNetwork import QNetworkReply
from PyQt4.QtNetwork import QNetworkRequest
from subprocess import Popen

sys.dont_write_bytecode = True
from GoogleMercatorProjection import getCorners             # NOQA
import ApiKeys                                              # NOQA
import DarkSkyProvider as darksky
import mqtt_fetch
isMqttRun = False

intHourlyData = 3   # interval in hours between hourly data to display
numHourlyData = 3   # number of hourly data records to store
numHourlyDisp = 3   # number of hourly data records to display
numDailyData  = 10  # number of daily data records to store
numDailyDisp  = 3   # number of daily data records to display
maxDailyDisp  = 6   # number to display when there are no hourly forecast displays
numHourly = numHourlyDisp
fcst_hours_delta = intHourlyData    # num hours between the hourly forecast displays
fcst_hours_0 = 2    # first hour after present time for hourly forecast
numDaily = numDailyDisp   # was 5
fcst_hours = range(fcst_hours_0,fcst_hours_0+numHourly*fcst_hours_delta,fcst_hours_delta)
fcst_days  = range(0,numDaily)
#iconAspect = Qt.IgnoreAspectRatio
iconAspect = Qt.KeepAspectRatio
onlyDaily = False   # forecast displays are mix of hourly and daily or only daily

def wind_cardinal(degrees):
    wd = {
        0:  'N',
        45: 'NE',
        90: 'E',
        135:    'SE',
        180:    'S',
        225:    'SW',
        270:    'W',
        315:    'NW',
        360:    'N'
    }
    d = 45 * int((degrees /45.0) + 0.5)
    logger.debug('wind_cardinal: %f -> %s' %(degrees,wd[d]))
    return wd[d]
        
class CurrentObsDisp(QtGui.QLabel):
    '''
    Create the display boxes for current observations.
    '''
    def __init__(self,parent,bSmall):
        QtGui.QLabel.__init__(self, parent)
        objName = "curr_obs"
        self.setObjectName(objName)
        self.small = bSmall
        frame = parent
        if bSmall:
            # Page with clock in center
            # datex displays "Thursday March 15th 2018".
            # It is large font, positioned at top center of screen
            self.datex = QtGui.QLabel(frame)
            self.datex.setObjectName("datex")
            self.datex.setStyleSheet("#datex { font-family:sans-serif; color: " +
                                Config.textcolor +
                                "; background-color: transparent; font-size: " +
                                str(int(50 * xscale)) +
                                "px; " +
                                Config.fontattr +
                                "}")
            self.datex.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.datex.setGeometry(0, 0, width, 100)

            # wxicon - a large weather icon (150x150) near top-left
            # TODO: awful - what is current value of ypos? Should be passed to init
            ypos = -25
            wxiconSize = 150
            self.wxicon = QtGui.QLabel(frame)
            self.wxicon.setObjectName("wxicon")
            self.wxicon.setStyleSheet("#wxicon { background-color: transparent; }")
            self.wxicon.setGeometry(75 * xscale, ypos * yscale, wxiconSize * xscale, wxiconSize * yscale)
            #self.wxicon.setGeometry(75 * xscale, ypos * yscale, 100 * xscale, 100 * yscale)

            # Text description of weather, e.g., "Sunny"
            if wxiconSize == 150:
                ypos += 110
            elif wxiconSize == 100:
                ypos += 80
            else:
                ypos += 80
            self.wxdesc = QtGui.QLabel(frame)
            self.wxdesc.setObjectName("wxdesc")
            self.wxdesc.setStyleSheet("#wxdesc { background-color: transparent; color: " +
                                 Config.textcolor +
                                 "; font-size: " +
                                 str(int(40 * xscale)) +
                                 "px; " +
                                 Config.fontattr +
                                 "}")
            self.wxdesc.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.wxdesc.setGeometry(3 * xscale, ypos * yscale, 300 * xscale, 100)

            # Current temperature from Wunderground
            ypos += 60
            self.temper = QtGui.QLabel(frame)
            self.temper.setObjectName("temper")
            self.temper.setStyleSheet("#temper { background-color: transparent; color: " +
                                 Config.textcolor +
                                 "; font-size: " +
                                 str(int(50 * xscale)) +
                                 "px; " +
                                 Config.fontattr +
                                 "}")
            self.temper.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.temper.setGeometry(3 * xscale, ypos * yscale, 330 * xscale, 100)

            # Current pressure from Wunderground
            # if font-size 25, ypos+=60
            ypos += 60
            self.press = QtGui.QLabel(frame)
            self.press.setObjectName("press")
            self.press.setStyleSheet("#press { background-color: transparent; color: " +
                                Config.textcolor +
                                "; font-size: " +
                                str(int(50 * xscale)) +
                                "px; " +
                                Config.fontattr +
                                "}")
            self.press.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.press.setGeometry(3 * xscale, ypos * yscale, 330 * xscale, 100)

            # Current humidity from Wunderground
            # if font-size 25, ypos += 30
            ypos += 60
            self.humidity = QtGui.QLabel(frame)
            self.humidity.setObjectName("humidity")
            self.humidity.setStyleSheet("#humidity { background-color: transparent; color: " +
                                   Config.textcolor +
                                   "; font-size: " +
                                   str(int(50 * xscale)) +
                                   "px; " +
                                   Config.fontattr +
                                   "}")
            self.humidity.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.humidity.setGeometry(3 * xscale, ypos * yscale, 330 * xscale, 100)

            # Current winds: direction, speed, gust speed
            # if font-size 20, ypos += 30
            ypos += 60
            self.wind = QtGui.QLabel(frame)
            self.wind.setObjectName("wind")
            self.wind.setStyleSheet("#wind { background-color: transparent; color: " +
                               Config.textcolor +
                               "; font-size: " +
                               str(int(40 * xscale)) +
                               "px; " +
                               Config.fontattr +
                               "}")
            self.wind.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.wind.setGeometry(3 * xscale, ypos * yscale, 300 * xscale, 100)

            # wind2 - this is the "feels_like" temperature, based on wind speed
            # if font-size 20, ypos += 20
            ypos += 100 # previous display field takes 2 lines
            self.wind2 = QtGui.QLabel(frame)
            self.wind2.setObjectName("wind2")
            self.wind2.setStyleSheet("#wind2 { background-color: transparent; color: " +
                                Config.textcolor +
                                "; font-size: " +
                                str(int(40 * xscale)) +
                                "px; " +
                                Config.fontattr +
                                "}")
            self.wind2.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.wind2.setGeometry(3 * xscale, ypos * yscale, 300 * xscale, 100)

            # wdate - shows current time and date + hourly and daily precip
            # if font-size 20, ypos += 20
            ypos += 50
            self.wdate = QtGui.QLabel(frame)
            self.wdate.setObjectName("wdate")
            self.wdate.setStyleSheet("#wdate { background-color: transparent; color: " +
                                Config.textcolor +
                                "; font-size: " +
                                str(int(40 * xscale)) +
                                "px; " +
                                Config.fontattr +
                                "}")
            self.wdate.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.wdate.setGeometry(3 * xscale, ypos * yscale, 350 * xscale, 100)
        else:
            # Large display shown when radar is also large size
            # datex2 displays "Thursday March 15th 2018".
            # It is large font, positioned at bottom right of screen when radar is full-scrren
            self.datex2 = QtGui.QLabel(frame)
            self.datex2.setObjectName("datex2")
            self.datex2.setStyleSheet("#datex2 { font-family:sans-serif; color: " +
                                 Config.textcolor +
                                 "; background-color: transparent; font-size: " +
                                 str(int(50 * xscale)) + "px; " +
                                 Config.fontattr +
                                 "}")
            self.datex2.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.datex2.setGeometry(800 * xscale, 780 * yscale, 640 * xscale, 100)
            self.datey2 = QtGui.QLabel(frame)
            self.datey2.setObjectName("datey2")
            self.datey2.setStyleSheet("#datey2 { font-family:sans-serif; color: " +
                                 Config.textcolor +
                                 "; background-color: transparent; font-size: " +
                                 str(int(50 * xscale)) +
                                 "px; " +
                                 Config.fontattr +
                                 "}")
            self.datey2.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.datey2.setGeometry(800 * xscale, 840 * yscale, 640 * xscale, 100)

            # wxicon2 - a large weather icon (150x150) near bottom-left when radar is full-screen
            self.wxicon2 = QtGui.QLabel(frame)
            self.wxicon2.setObjectName("wxicon2")
            self.wxicon2.setStyleSheet("#wxicon2 { background-color: transparent; }")
            self.wxicon2.setGeometry(0 * xscale, 750 * yscale, 150 * xscale, 150 * yscale)

            self.wxdesc2 = QtGui.QLabel(frame)
            self.wxdesc2.setObjectName("wxdesc2")
            self.wxdesc2.setStyleSheet("#wxdesc2 { background-color: transparent; color: " +
                                  Config.textcolor +
                                  "; font-size: " +
                                  str(int(50 * xscale)) +
                                  "px; " +
                                  Config.fontattr +
                                  "}")
            self.wxdesc2.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.wxdesc2.setGeometry(400 * xscale, 800 * yscale, 400 * xscale, 100)

            self.temper2 = QtGui.QLabel(frame)
            self.temper2.setObjectName("temper2")
            self.temper2.setStyleSheet("#temper2 { background-color: transparent; color: " +
                                  Config.textcolor +
                                  "; font-size: " +
                                  str(int(70 * xscale)) +
                                  "px; " +
                                  Config.fontattr +
                                  "}")
            self.temper2.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.temper2.setGeometry(125 * xscale, 780 * yscale, 300 * xscale, 100)
        
    def fill_obs(self,currObs):
        data = currObs.getObsStr('icon')
        if data:
            logger.debug('icon = %s' %(data))
            wxiconpixmap = QtGui.QPixmap(data)
        if self.small:
            self.wxicon.setPixmap(wxiconpixmap.scaled(
                self.wxicon.width(), self.wxicon.height(), iconAspect,
                Qt.SmoothTransformation))
            self.wxdesc.setText(currObs.getObsStr('wx_text'))
            self.temper.setText(currObs.getObsStr('temp'))
            if currObs.getObsStr('press_trend'):
                self.press.setText(Config.LPressure + currObs.getObsStr('press') + ' ' + currObs.getObsStr('press_trend'))
            else:
                self.press.setText(Config.LPressure + currObs.getObsStr('press'))
            self.humidity.setText(Config.LHumidity + currObs.getObsStr('rel_hum'))
            if Config.wind_degrees:
                wd = currObs.getObsStr('wind_degrees')
                wd = wind_cardinal(float(wd))
            else:
                wd = currObs.getObsStr('wind_dir')
            self.wind.setText(Config.LWind +
                         wd + ' ' +
                         str(currObs.getObsStr('wind_speed')) +
                         '\n' + Config.Lgusting +
                         str(currObs.getObsStr('wind_gust')))
            self.wind2.setText(Config.LFeelslike + currObs.getObsStr('temp_feels_like'))
            self.wdate.setText(Config.LPrecip1hr + currObs.getObsStr('precip_1hr'))
        else:
            self.wxicon2.setPixmap(wxiconpixmap.scaled(
                self.wxicon2.width(), self.wxicon2.height(), iconAspect,
                Qt.SmoothTransformation))
            self.wxdesc2.setText(currObs.getObsStr('wx_text'))
            self.temper2.setText(currObs.getObsStr('temp'))
        
# Create boxes on right side that contain forecasts for different time periods, 'i'.
# Evidently each box contains smaller areas named "icon", "wx", "wx2", "day"
# I guess these regions are later filled with data.
class FcstDisp(QtGui.QLabel):
    boxWidth = 340
    textHeight = 20
    def __init__(self,parent,i):
        '''
        :param parent: the QtGui object that holds this FcstDisp object
        :param i: the index of this object, becomes part of ObjectName
        '''
        QtGui.QLabel.__init__(self, parent)
        objName = "forecast"+str(i)
        self.setObjectName(objName)
        style = "%s { background-color: transparent; color:%s; font-size:%dpx; %s; border:1px solid rgb(0, 255, 255);}" \
                %(objName,Config.textcolor,int(self.textHeight * xscale),Config.fontattr)
        styleFmt = "#{0} {{ background-color: transparent; color:{1}; font-size:{2}px; {3}; border:1px solid rgb(0, 255, 255);}}"
        style1 = styleFmt.format(objName,Config.textcolor,int(self.textHeight * xscale),Config.fontattr)
        self.setStyleSheet(style1)
        # Set the screen coordinates of the box (xorigin,yorigin,width,height)
        self.setGeometry(width-(self.boxWidth*xscale)+6, i * ht_forecast * yscale,
                        (self.boxWidth*xscale)-12, ht_forecast * yscale)
        # Now define the contents of FcstDisp box
        # icon: displays a weather icon: cloud, sun, rain, etc.
        icon = QtGui.QLabel(self)
        icon.setStyleSheet("#icon { background-color: transparent; }")
        icon.setGeometry(0, 0, 100 * xscale, ht_forecast * yscale)
        icon.setObjectName("icon")

        textStyle = "background-color: transparent; color:%s; font-size:%spx; %s; " %(Config.textcolor,str(int(25 * xscale)),Config.fontattr)
        # wx: text that spells out some of the forecast
        wx = QtGui.QLabel(self)
        wx.setStyleSheet("#wx {%s}" %(textStyle))
        #wx.setGeometry(100 * xscale, 10 * yscale, 200 * xscale, 20 * yscale)
        wx.setGeometry(2, 10 * yscale, self.boxWidth * xscale, 20 * yscale)
        wx.setObjectName("wx")

        # wx2: text that spells out some of the forecast
        wx2 = QtGui.QLabel(self)
        wx2.setStyleSheet("#wx2 {%s}" %(textStyle))
        wx2.setGeometry(100 * xscale, 30 * yscale, 200 * xscale, ht_forecast * yscale)
        wx2.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        wx2.setWordWrap(True)
        wx2.setObjectName("wx2")

        # day: date and day of the week
        day = QtGui.QLabel(self)
        day.setStyleSheet("#day {%s}" %(textStyle))
        #day.setGeometry(100 * xscale, 75 * yscale, 200 * xscale, 25 * yscale)
        day.setGeometry(100 * xscale, ht_forecast * yscale - 25, 200 * xscale, 25 * yscale)
        day.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        day.setObjectName("day")

    def fill_daily_fcst_box(self,f):
        '''
        :param f: the forecast object from Wunderground
        Decode the Wunderground forecast and write into the forecast box.
        The Wunderground API returns JSON. It seems really sloppy, because there are
        different keys depending on if it's an hourly or daily forecast.
        '''
        global iconAspect
        icon = self.findChild(QtGui.QLabel,"icon")
        logger.debug('icon = %s' %(f.getObsStr('icon')))
        wxiconpixmap = QtGui.QPixmap(f.getObsStr('icon'))
        icon.setPixmap(wxiconpixmap.scaled(
            icon.width(),
            icon.height(),
            iconAspect,
            Qt.SmoothTransformation))
        # Show conditions, such as "clear" or "cloudy"
        wx = self.findChild(QtGui.QLabel, "wx")
        wx.setText(f.getObsStr('wx_text'))
        # Show the day name + time if hourly forecast
        day = self.findChild(QtGui.QLabel, "day")
        # TODO: not best way to do this, should happen in DarkSkyProvider
        epoch = f.getObsStr('day') # returns epoch time
        dt = datetime.datetime.fromtimestamp(float(epoch))
        day.setText(str(dt.strftime('%a')))   # TODO: we're missing f['FCTTIME']['civil']
        # Show precip forecast and temperature. If daily, then show temp range.
        wx2 = self.findChild(QtGui.QLabel, "wx2")
        s = ''
        s += f.getObsStr('pop') + ' '     # TODO: we need special handling when pop==0.0
        # TODO: need special handling if snow or qpf == 0.0
        snow = f.getObsStr('snow')
        if snow and len(snow) > 0:
            s += Config.LSnow + f.getObsStr('snow')+ ' '
        qpf = f.getObsStr('qpf')
        if qpf and len(qpf) > 0:
            s += Config.LRain + f.getObsStr('qpf') + ' '
        s += f.getObsStr('temp_high') + '/' + f.getObsStr('temp_low')

        wx2.setText(s)

    def fill_hourly_fcst_box(self,f):
        '''
        :param f: the forecast object from Wunderground
        Decode the Wunderground forecast and write into the forecast box.
        The Wunderground API returns JSON. It seems really sloppy, because there are
        different keys depending on if it's an hourly or daily forecast.
        '''
        global iconAspect
        icon = self.findChild(QtGui.QLabel,"icon")
        logger.debug('icon = %s' %(f.getObsStr('icon')))
        wxiconpixmap = QtGui.QPixmap(f.getObsStr('icon'))
        icon.setPixmap(wxiconpixmap.scaled(
            icon.width(),
            icon.height(),
            iconAspect,
            Qt.SmoothTransformation))
        # Show conditions, such as "clear" or "cloudy"
        wx = self.findChild(QtGui.QLabel, "wx")
        wx.setText(f.getObsStr('wx_text'))
        # Show the day name + time if hourly forecast
        day = self.findChild(QtGui.QLabel, "day")
        epoch = f.getObsStr('hour') # returns epoch time
        dt = datetime.datetime.fromtimestamp(float(epoch))
        day.setText(str(dt.strftime('%a %HH')))   # TODO: we're missing f['FCTTIME']['civil']
        #day.setText(f.getObsStr('day')+' '+f.getObsStr('hour'))   # TODO: we're missing f['FCTTIME']['civil']
        #day.setText(f.getObsStr('hour'))   # TODO: we're missing f['FCTTIME']['civil']
        # Show precip forecast and temperature. If daily, then show temp range.
        wx2 = self.findChild(QtGui.QLabel, "wx2")
        s = ''
        s += f.getObsStr('pop') + ' '     # TODO: we need special handling when pop==0.0
        # TODO: need special handling if snow or qpf == 0.0
        snow = f.getObsStr('snow')
        if snow and len(snow) > 0:
            s += Config.LSnow + f.getObsStr('snow')+ ' '
        qpf = f.getObsStr('qpf')
        if qpf and len(qpf) > 0:
            s += Config.LRain + f.getObsStr('qpf') + ' '
        s += f.getObsStr('temp')

        wx2.setText(s)
        
    def mousePressEvent(self, event):
        global onlyDaily
        if type(event) == QtGui.QMouseEvent:
            if event.button() == Qt.LeftButton:
                onlyDaily = not onlyDaily
                updateFcstDisp()
            elif event.button() == Qt.RightButton:
                pass
    

def tick():
    '''
    Update the clock display
    '''
    global hourpixmap, minpixmap, secpixmap
    global hourpixmap2, minpixmap2, secpixmap2
    global lastmin, lastday, lasttimestr
    global clockrect
    global datex, datex2, datey2, pdy

    if Config.DateLocale != "":
        try:
            locale.setlocale(locale.LC_TIME, Config.DateLocale)
        except:
            pass

    now = datetime.datetime.now()
    if Config.digital:
        timestr = Config.digitalformat.format(now)
        if Config.digitalformat.find("%I") > -1:
            if timestr[0] == '0':
                timestr = timestr[1:99]
        if lasttimestr != timestr:
            clockface.setText(timestr.lower())
        lasttimestr = timestr
    else:
        angle = now.second * 6
        ts = secpixmap.size()
        secpixmap2 = secpixmap.transformed(
            QtGui.QMatrix().scale(
                float(clockrect.width()) / ts.height(),
                float(clockrect.height()) / ts.height()
            ).rotate(angle),
            Qt.SmoothTransformation
        )
        sechand.setPixmap(secpixmap2)
        ts = secpixmap2.size()
        sechand.setGeometry(
            clockrect.center().x() - ts.width() / 2,
            clockrect.center().y() - ts.height() / 2,
            ts.width(),
            ts.height()
        )
        if now.minute != lastmin:
            lastmin = now.minute
            angle = now.minute * 6
            ts = minpixmap.size()
            minpixmap2 = minpixmap.transformed(
                QtGui.QMatrix().scale(
                    float(clockrect.width()) / ts.height(),
                    float(clockrect.height()) / ts.height()
                ).rotate(angle),
                Qt.SmoothTransformation
            )
            minhand.setPixmap(minpixmap2)
            ts = minpixmap2.size()
            minhand.setGeometry(
                clockrect.center().x() - ts.width() / 2,
                clockrect.center().y() - ts.height() / 2,
                ts.width(),
                ts.height()
            )

            angle = ((now.hour % 12) + now.minute / 60.0) * 30.0
            ts = hourpixmap.size()
            hourpixmap2 = hourpixmap.transformed(
                QtGui.QMatrix().scale(
                    float(clockrect.width()) / ts.height(),
                    float(clockrect.height()) / ts.height()
                ).rotate(angle),
                Qt.SmoothTransformation
            )
            hourhand.setPixmap(hourpixmap2)
            ts = hourpixmap2.size()
            hourhand.setGeometry(
                clockrect.center().x() - ts.width() / 2,
                clockrect.center().y() - ts.height() / 2,
                ts.width(),
                ts.height()
            )

    dy = "{0:%I:%M %p}".format(now)
    if dy != pdy:
        pdy = dy
        datey2.setText(dy)

    if now.day != lastday:
        lastday = now.day
        # date
        sup = 'th'
        if (now.day == 1 or now.day == 21 or now.day == 31):
            sup = 'st'
        if (now.day == 2 or now.day == 22):
            sup = 'nd'
        if (now.day == 3 or now.day == 23):
            sup = 'rd'
        if Config.DateLocale != "":
            sup = ""
        ds = "{0:%A %B} {0.day}<sup>{1}</sup> {0.year}".format(now, sup)
        datex.setText(ds)
        datex2.setText(ds)

#mqtt_fetch.run_as_service()
def getMqtt():
    '''
    Fetch environmental data using MQTT.
    :return: tuple (timestamp, temperature, humidity)
    '''
    global isMqttRun
    if not isMqttRun:
        mqtt_fetch.run_as_service()
        isMqttRun = True
    if False:
        ts = time.time()
        temp = 70.1
        humid = 50.5
    else:
        if 'time' in mqtt_fetch.msg_dict:
            ts = mqtt_fetch.msg_dict['time']
        else:
            ts = -1.0
        if 'temp' in mqtt_fetch.msg_dict:
            temp = float(mqtt_fetch.msg_dict['temp'])
            temp = 9.0/5.0 * temp + 32.0
        else:
            temp = 0.0
        if 'rel_hum' in mqtt_fetch.msg_dict:
            humid = float(mqtt_fetch.msg_dict['rel_hum'])
        else:
            humid = 0.0
    return ts,temp,humid

def tempfinished():
    global tempreply, tempHouse
    timestamp,t,h = getMqtt()
    if abs(time.time() - timestamp) < 65.0:
        tempHouse.setText('Temp=%.1f, Hum=%d%%' %(t,int(h)))
    else:
        tempHouse.setText('Temp sensor offline')
    '''
    if tempreply.error() != QNetworkReply.NoError:
        return
    tempstr = str(tempreply.readAll())
    tempdata = json.loads(tempstr)
    if tempdata['temp'] == '':
        return
    if Config.metric:
        s = Config.LInsideTemp + \
            "%3.1f" % ((float(tempdata['temp']) - 32.0) * 5.0 / 9.0)
        if tempdata['temps']:
            if len(tempdata['temps']) > 1:
                s = ''
                for tk in tempdata['temps']:
                    s += ' ' + tk + ':' + \
                        "%3.1f" % (
                            (float(tempdata['temps'][tk]) - 32.0) * 5.0 / 9.0)
    else:
        s = Config.LInsideTemp + tempdata['temp']
        if tempdata['temps']:
            if len(tempdata['temps']) > 1:
                s = ''
                for tk in tempdata['temps']:
                    s += ' ' + tk + ':' + tempdata['temps'][tk]
    tempHouse.setText(s)
    '''

def gettemp():
    '''
    global tempreply
    host = 'localhost'
    if platform.uname()[1] == 'KW81':
        host = 'piclock.local'  # this is here just for testing
    r = QUrl('http://' + host + ':48213/temp')
    r = QNetworkRequest(r)
    tempreply = manager.get(r)
    tempreply.finished.connect(tempfinished)
    '''
    tempfinished()
    
def debugPrint(bugFile,theString):
    bugFile.write(theString)
    bugFile.write('\n')

'''
Notes on the JSON returned by wunderground.
- Apparently 'forecast' returns 10 days. There is a single array 'forecastday' and within it
  are dict objects that are designated simply by "period":<N>, where N runs from 0 to 19.
  These forecast periods apparently are simply daytime and nighttime forecasts for each day.
- But also 'forecast' object contains 'simpleforecast'. This is a dict that contains an array
  named 'forecastday', and it contains a lot more info than the other 'forecastday'.
  Here there is only one forecast per day, and they are numbered 1 to 10.
  I made a request at 1330 PST and these forecasts came back wit a time of 1900 PST - I wonder why?
- 'hourly_forecast' returns 10 days, with a FCTTIME tag for every hour of every day.
'''
def wxfinished():
    global wxreply, wxdata
    global wxicon, temper, wxdesc, press, humidity
    global wind, wind2, wdate, bottom, forecast
    global wxicon2, temper2, wxdesc2
    global wxProvider

    wxdata = wxProvider.getData()
    if True:
        # primary keys in wxdata
        wx_keys = []
        for wx_key in wxdata:
            wx_keys.append(wx_key)
        logger.debug('wx_keys = %s' %(str(wx_keys)))
    if False:
        # GDN: I wonder what's in there? Let's write to file and find out.
        bugFile = open('debug.log','w')
        debugPrint(bugFile,wxstr)
        bugFile.close()
    currObs = darksky.CurrentObs(wxdata)
    currObsDispSmall.fill_obs(currObs)
    currObsDispBig.fill_obs(currObs)
    """
    bottom.setText(Config.LSunRise +
                   wxdata['sun_phase']['sunrise']['hour'] + ':' +
                   wxdata['sun_phase']['sunrise']['minute'] +
                   Config.LSet +
                   wxdata['sun_phase']['sunset']['hour'] + ':' +
                   wxdata['sun_phase']['sunset']['minute'] +
                   Config.LMoonPhase +
                   wxdata['moon_phase']['phaseofMoon']
                   )
    """
    
    updateFcstDisp()

def updateFcstDisp():
    '''
    Called by a mouse click somewhere.
    Will display either mix of hourly and daily forecasts or only daily forecasts.
    '''
    global wxdata, onlyDaily, numDaily, numHourly
    if onlyDaily:
        numDaily = maxDailyDisp
        # Fill next boxes with future daily forecasts
        for i in range(0, numDaily):
            #f = wxdata['daily'][i]
            fcstDisp = forecast[i]
            daily = darksky.FcstDailyData(wxdata,i)
            fcstDisp.fill_daily_fcst_box(daily)
    else:
        numDaily = numDailyDisp
        # Fill first few boxes with today forecasts
        for i in range(0, numHourly):
            #f = wxdata['hourly'][i * 3 + 2]    # every 3 hours
            fcstDisp = forecast[i]
            hourly = darksky.FcstHourlyData(wxdata,i*3+2)
            fcstDisp.fill_hourly_fcst_box(hourly)

        # Fill next boxes with future daily forecasts
        for i in range(0, numDaily):
            #f = wxdata['daily'][i]
            fcstDisp = forecast[i+numHourly]
            daily = darksky.FcstDailyData(wxdata,i)
            fcstDisp.fill_daily_fcst_box(daily)

wxProvider = darksky.WxData()
    
def getwx():
    '''
    Get weather forecasts from Weather Underground.
    Returns a big JSON blob.
    Calls wxfinished when ready.
    '''
    # GDN: apparently wunderground API can simply fetch both hourly and 10 day
    # forecast in one call.
    global wxurl
    global wxreply
    global wxProvider
    logger.info("getting current and forecast:" + time.ctime())
    # Refer to wunderground API docs: https://www.wunderground.com/weather/api/d/docs?d=data/forecast10day
    # Each of the queries returns a lot of JSON. I'm going to list the expected returns.
    '''
    conditions: current_observation + <details>
    astronomy: moon_phase, sunrise, sunset
    hourly10day: hourly_forecast:FCTTIME + <various forecast values>
    forecast10day: forecast:txt_forecast:forecastday and forecast:simpleforecast:forecastday
    '''
    wxProvider.getwx()
    if wxProvider.hasData:
        wxfinished()

def getallwx():
    getwx()


def qtstart():
    global ctimer, wxtimer, temptimer
    global manager
    global objradar1
    global objradar2
    global objradar3
    global objradar4

    getallwx()

    gettemp()

    objradar1.start(Config.radar_refresh * 60)
    objradar1.wxstart()
    if objradar2:
        objradar2.start(Config.radar_refresh * 60)
        objradar2.wxstart()
    objradar3.start(Config.radar_refresh * 60)
    objradar4.start(Config.radar_refresh * 60)

    # Clock timer. Whenever the timer runs out, call 'tick' function
    ctimer = QtCore.QTimer()
    ctimer.timeout.connect(tick)
    ctimer.start(1000)  # 1000 ms

    wxtimer = QtCore.QTimer()
    wxtimer.timeout.connect(getallwx)
    wxtimer.start(1000 * 60 * Config.weather_refresh + random.uniform(1000, 10000))

    temptimer = QtCore.QTimer()
    temptimer.timeout.connect(gettemp)
    temptimer.start(1000 * 60 * Config.home_refresh + random.uniform(1000, 10000))


class Radar(QtGui.QLabel):

    def __init__(self, parent, radar, rect, myname):
        global xscale, yscale
        self.myname = myname
        self.rect = rect
        self.satellite = Config.satellite
        try:
            if radar["satellite"]:
                self.satellite = 1
        except KeyError:
            pass
        self.baseurl = self.mapurl(radar, rect, False)
        logger.debug("google map base url: " + self.baseurl)
        self.mkurl = self.mapurl(radar, rect, True)
        self.wxurl = self.radarurl(radar, rect)
        logger.debug("radar url: " + self.wxurl)
        QtGui.QLabel.__init__(self, parent)
        self.interval = Config.radar_refresh * 60
        self.lastwx = 0
        self.retries = 0

        self.setObjectName("radar")
        self.setGeometry(rect)
        #self.setStyleSheet("#radar { background-color: grey; }")
        # next: setting margin results in a grey border and the inside image spills past the margin
        #self.setStyleSheet("#radar { background-color: grey; border-width:3px; border-color: solid rgb(255, 255, 0); margin: 3px;}")
        # next: without margin, I get no border at all
        #self.setStyleSheet("#radar { background-color: grey; border-width:3px; border-color: solid rgb(255, 255, 0);}")
        # next: with border-style I get side borders, but not top and bottom
        self.setStyleSheet("#radar { background-color: transparent; border-width:3px; border-color: solid rgb(255, 255, 0); border-style: solid;}")
        self.setAlignment(Qt.AlignCenter)

        self.wwx = QtGui.QLabel(self)
        self.wwx.setObjectName("wx")
        # use padding or margin?
        #self.wwx.setStyleSheet("#wx { background-color: transparent; padding:4px; border-width:3px; border-color: solid rgb(255, 255, 0); border-style: outset;}")
        #self.wwx.setStyleSheet("#wx { background-color: transparent; border-width:3px; border-color: solid rgb(255, 255, 0); border-style: outset;}")
        self.wwx.setStyleSheet("#wx { background-color: transparent;}")
        self.wwx.setGeometry(0, 0, rect.width(), rect.height())

        self.wmk = QtGui.QLabel(self)
        self.wmk.setObjectName("mk")
        self.wmk.setStyleSheet("#mk { background-color: transparent; }")
        self.wmk.setGeometry(0, 0, rect.width(), rect.height())

        self.wxmovie = QMovie()

    def mapurl(self, radar, rect, markersonly):
        # 'https://maps.googleapis.com/maps/api/staticmap?maptype=hybrid&center='+rcenter.lat+','+rcenter.lng+'&zoom='+rzoom+'&size=300x275'+markersr;
        urlp = []

        if len(ApiKeys.googleapi) > 0:
            urlp.append('key=' + ApiKeys.googleapi)
        urlp.append(
            'center=' + str(radar['center'].lat) +
            ',' + str(radar['center'].lng))
        zoom = radar['zoom']
        rsize = rect.size()
        if rsize.width() > 640 or rsize.height() > 640:
            rsize = QtCore.QSize(rsize.width() / 2, rsize.height() / 2)
            zoom -= 1
        urlp.append('zoom=' + str(zoom))
        urlp.append('size=' + str(rsize.width()) + 'x' + str(rsize.height()))
        if markersonly:
            urlp.append('style=visibility:off')
        else:
            urlp.append('maptype=hybrid')
        for marker in radar['markers']:
            marks = []
            for opts in marker:
                if opts != 'location':
                    marks.append(opts + ':' + marker[opts])
            marks.append(str(marker['location'].lat) +
                         ',' + str(marker['location'].lng))
            urlp.append('markers=' + '|'.join(marks))

        return 'http://maps.googleapis.com/maps/api/staticmap?' + \
            '&'.join(urlp)

    def radarurl(self, radar, rect):
        # wuprefix = 'http://api.wunderground.com/api/';
        # wuprefix+wuapi+'/animatedradar/image.gif?maxlat='+rNE.lat+'&maxlon='+
        #       rNE.lng+'&minlat='+rSW.lat+'&minlon='+rSW.lng+wuoptionsr;
        # wuoptionsr = '&width=300&height=275&newmaps=0&reproj.automerc=1&num=5
        #       &delay=25&timelabel=1&timelabel.y=10&rainsnow=1&smooth=1';
        rr = getCorners(radar['center'], radar['zoom'],
                        rect.width(), rect.height())
        if self.satellite:
            return (Config.wuprefix + ApiKeys.wuapi +
                    '/animatedsatellite/lang:' +
                    Config.wuLanguage +
                    '/image.gif' +
                    '?maxlat=' + str(rr['N']) +
                    '&maxlon=' + str(rr['E']) +
                    '&minlat=' + str(rr['S']) +
                    '&minlon=' + str(rr['W']) +
                    '&width=' + str(rect.width()) +
                    '&height=' + str(rect.height()) +
                    '&newmaps=0&reproj.automerc=1&num=5&delay=25' +
                    '&timelabel=1&timelabel.y=20&smooth=1&key=sat_ir4_bottom'
                    )
        else:
            return (Config.wuprefix +
                    ApiKeys.wuapi +
                    '/animatedradar/lang:' +
                    Config.wuLanguage + '/image.gif' +
                    '?maxlat=' + str(rr['N']) +
                    '&maxlon=' + str(rr['E']) +
                    '&minlat=' + str(rr['S']) +
                    '&minlon=' + str(rr['W']) +
                    '&width=' + str(rect.width()) +
                    '&height=' + str(rect.height()) +
                    '&newmaps=0&reproj.automerc=1&num=5&delay=25' +
                    '&timelabel=1&timelabel.y=20&rainsnow=1&smooth=1' +
                    '&radar_bitmap=1&xnoclutter=1&xnoclutter_mask=1&cors=1'
                    )

    def basefinished(self):
        if self.basereply.error() != QNetworkReply.NoError:
            return
        self.basepixmap = QPixmap()
        self.basepixmap.loadFromData(self.basereply.readAll())
        if self.basepixmap.size() != self.rect.size():
            self.basepixmap = self.basepixmap.scaled(self.rect.size(),
                                                     iconAspect,
                                                     Qt.SmoothTransformation)
        if self.satellite:
            p = QPixmap(self.basepixmap.size())
            p.fill(Qt.transparent)
            painter = QPainter()
            painter.begin(p)
            painter.setOpacity(0.6)
            painter.drawPixmap(0, 0, self.basepixmap)
            painter.end()
            self.basepixmap = p
            self.wwx.setPixmap(self.basepixmap)
        else:
            self.setPixmap(self.basepixmap)

    def mkfinished(self):
        if self.mkreply.error() != QNetworkReply.NoError:
            return
        self.mkpixmap = QPixmap()
        self.mkpixmap.loadFromData(self.mkreply.readAll())
        if self.mkpixmap.size() != self.rect.size():
            self.mkpixmap = self.mkpixmap.scaled(
                self.rect.size(),
                iconAspect,
                Qt.SmoothTransformation)
        br = QBrush(QColor(Config.dimcolor))
        painter = QPainter()
        painter.begin(self.mkpixmap)
        painter.fillRect(0, 0, self.mkpixmap.width(),
                         self.mkpixmap.height(), br)
        painter.end()
        self.wmk.setPixmap(self.mkpixmap)

    def wxfinished(self):
        if self.wxreply.error() != QNetworkReply.NoError:
            logger.error("get radar error " + self.myname + ":" + str(self.wxreply.error()))
            self.lastwx = 0
            return
        logger.debug("radar map received:" + self.myname + ":" + time.ctime())
        self.wxmovie.stop()
        self.wxdata = QtCore.QByteArray(self.wxreply.readAll())
        self.wxbuff = QtCore.QBuffer(self.wxdata)
        self.wxbuff.open(QtCore.QIODevice.ReadOnly)
        mov = QMovie(self.wxbuff, 'GIF')
        logger.debug("radar map frame count:" + self.myname + ":" + \
            str(mov.frameCount()) + ":r" + str(self.retries))
        if mov.frameCount() > 2:
            self.lastwx = time.time()
            self.retries = 0
        else:
            # radar image retrieval failed
            if self.retries > 3:
                # give up, last successful animation stays.
                # the next normal radar_refresh time (default 10min) will apply
                self.lastwx = time.time()
                return

            self.lastwx = 0
            # count retries
            self.retries = self.retries + 1
            # retry in 5 seconds
            QtCore.QTimer.singleShot(5 * 1000, self.getwx)
            return
        self.wxmovie = mov
        if self.satellite:
            self.setMovie(self.wxmovie)
        else:
            self.wwx.setMovie(self.wxmovie)
        if self.parent().isVisible():
            self.wxmovie.start()

    def getwx(self):
        global lastapiget
        i = 0.1
        # making sure there is at least 2 seconds between radar api calls
        lastapiget += 2
        if time.time() > lastapiget:
            lastapiget = time.time()
        else:
            i = lastapiget - time.time()
        logger.debug("get radar api call spacing oneshot get i=" + str(i))
        QtCore.QTimer.singleShot(i * 1000, self.getwx2)

    def getwx2(self):
        global manager
        try:
            if self.wxreply.isRunning():
                return
        except Exception:
            pass
        logger.debug("getting radar map " + self.myname + ":" + time.ctime())
        self.wxreq = QNetworkRequest(
            QUrl(self.wxurl + '&rrrand=' + str(time.time())))
        self.wxreply = manager.get(self.wxreq)
        QtCore.QObject.connect(self.wxreply, QtCore.SIGNAL(
            "finished()"), self.wxfinished)

    def getbase(self):
        global manager
        self.basereq = QNetworkRequest(QUrl(self.baseurl))
        self.basereply = manager.get(self.basereq)
        QtCore.QObject.connect(self.basereply, QtCore.SIGNAL(
            "finished()"), self.basefinished)

    def getmk(self):
        global manager
        self.mkreq = QNetworkRequest(QUrl(self.mkurl))
        self.mkreply = manager.get(self.mkreq)
        QtCore.QObject.connect(self.mkreply, QtCore.SIGNAL(
            "finished()"), self.mkfinished)

    def start(self, interval=0):
        if interval > 0:
            self.interval = interval
        self.getbase()
        self.getmk()
        self.timer = QtCore.QTimer()
        QtCore.QObject.connect(
            self.timer, QtCore.SIGNAL("timeout()"), self.getwx)

    def wxstart(self):
        logger.debug("wxstart for " + self.myname)
        if (self.lastwx == 0 or (self.lastwx + self.interval) < time.time()):
            self.getwx()
        # random 1 to 10 seconds added to refresh interval to spread the
        # queries over time
        i = (self.interval + random.uniform(1, 10)) * 1000
        self.timer.start(i)
        self.wxmovie.start()
        QtCore.QTimer.singleShot(1000, self.wxmovie.start)

    def wxstop(self):
        logger.debug("wxstop for " + self.myname)
        self.timer.stop()
        self.wxmovie.stop()

    def stop(self):
        try:
            self.timer.stop()
            self.timer = None
            if self.wxmovie:
                self.wxmovie.stop()
        except Exception:
            pass


def realquit():
    if True:
        # causes crash in Windows
        QtGui.QApplication.exit(0)
    else:
        # but this leaves some threads hanging
        exit()


def myquit(a=0, b=0):
    global objradar1, objradar2, objradar3, objradar4
    global ctimer, wtimer, temptimer

    objradar1.stop()
    if objradar2:
        objradar2.stop()
    objradar3.stop()
    objradar4.stop()
    ctimer.stop()
    wxtimer.stop()
    temptimer.stop()

    QtCore.QTimer.singleShot(30, realquit)


def fixupframe(frame, onoff):
    for child in frame.children():
        if isinstance(child, Radar):
            if onoff:
                # print "calling wxstart on radar on ",frame.objectName()
                child.wxstart()
            else:
                # print "calling wxstop on radar on ",frame.objectName()
                child.wxstop()

# GDN: the display has 2 frames only (4-Jan-2018).
# mousePressEvent anywhere within myMain will call this.
def nextframe(plusminus):
    global frames, framep
    frames[framep].setVisible(False)
    fixupframe(frames[framep], False)
    framep += plusminus
    if framep >= len(frames):
        framep = 0
    if framep < 0:
        framep = len(frames) - 1
    frames[framep].setVisible(True)
    fixupframe(frames[framep], True)


class myMain(QtGui.QWidget):

    def keyPressEvent(self, event):
        global weatherplayer, lastkeytime
        if isinstance(event, QtGui.QKeyEvent):
            # print event.key(), format(event.key(), '08x')
            if event.key() == Qt.Key_F4:
                myquit()
            if event.key() == Qt.Key_F2:
                if time.time() > lastkeytime:
                    if weatherplayer is None:
                        weatherplayer = Popen(
                            ["mpg123", "-q", Config.noaastream])
                    else:
                        weatherplayer.kill()
                        weatherplayer = None
                lastkeytime = time.time() + 2
            if event.key() == Qt.Key_Space:
                nextframe(1)
            if event.key() == Qt.Key_Left:
                nextframe(-1)
            if event.key() == Qt.Key_Right:
                nextframe(1)

    def mousePressEvent(self, event):
        if type(event) == QtGui.QMouseEvent:
            nextframe(1)

configname = 'Config'

if len(sys.argv) > 1:
    configname = sys.argv[1]

if not os.path.isfile(configname + ".py"):
    print("ERROR: Config file not found %s" % configname + ".py")
    exit(1)

Config = __import__(configname)

# define default values for new/optional config variables.

try:
    Config.metric
except AttributeError:
    Config.metric = 0

try:
    Config.weather_refresh
except AttributeError:
    Config.weather_refresh = 30   # minutes

try:
    Config.radar_refresh
except AttributeError:
    Config.radar_refresh = 10    # minutes

try:
    Config.fontattr
except AttributeError:
    Config.fontattr = ''

try:
    Config.dimcolor
except AttributeError:
    Config.dimcolor = QColor('#000000')
    Config.dimcolor.setAlpha(0)

try:
    Config.DateLocale
except AttributeError:
    Config.DateLocale = ''

try:
    Config.wind_degrees
except AttributeError:
    Config.wind_degrees = 0

try:
    Config.satellite
except AttributeError:
    Config.satellite = 0

try:
    Config.digital
except AttributeError:
    Config.digital = 0

try:
    Config.LPressure
except AttributeError:
    Config.wuLanguage = "EN"
    Config.LPressure = "Pressure "
    Config.LHumidity = "Humidity "
    Config.LWind = "Wind "
    Config.Lgusting = " gusting "
    Config.LFeelslike = "Feels like "
    Config.LPrecip1hr = " Precip 1hr:"
    Config.LToday = "Today: "
    Config.LSunRise = "Sun Rise:"
    Config.LSet = " Set: "
    Config.LMoonPhase = " Moon Phase:"
    Config.LInsideTemp = "Inside Temp "
    Config.LRain = " Rain: "
    Config.LSnow = " Snow: "
#


lastmin = -1
lastday = -1
pdy = ""
lasttimestr = ""
weatherplayer = None
lastkeytime = 0
lastapiget = time.time()

app = QtGui.QApplication(sys.argv)
if Config.bFullScreen:    # GDN
    desktop = app.desktop()
    rec = desktop.screenGeometry()
    height = rec.height()
    width = rec.width()

signal.signal(signal.SIGINT, myquit)

w = myMain()
if not Config.bFullScreen:    # GDN
    # GDN
    height = 480
    width  = 800
    w.resize(width,height)
# virtual app dimensions
vWidth = 1600.0
vHeight = 900.00
w.setWindowTitle(os.path.basename(__file__))

w.setStyleSheet("QWidget { background-color: black;}")

# fullbgpixmap = QtGui.QPixmap(Config.background)
# fullbgrect = fullbgpixmap.rect()
# xscale = float(width)/fullbgpixmap.width()
# yscale = float(height)/fullbgpixmap.height()

#xscale = float(width) / 1440.0
#yscale = float(height) / 900.0
xscale = float(width) / vWidth
yscale = float(height) / vHeight

frames = []
framep = 0

frame1 = QtGui.QFrame(w)
frame1.setObjectName("frame1")
frame1.setGeometry(0, 0, width, height)
# 1. correct aspect ratio, but image is centered toward lower-right
frame1_style = "background-color: black; border-image: url(%s) 0 0 0 0 repeat repeat;" %(Config.background)
# 2. incorrect aspect, image is centered
frame1_style = "background-color: black; border-image: url(%s);" %(Config.background)
# 3. same as 1
frame1_style = "background-color: black; border-image: url(%s) repeat repeat;" %(Config.background)
# 4. same as 2
frame1_style = "background-color: black; border-image: url(%s) 0 0 0 0;" %(Config.background)
# 5. same as 2
frame1_style = "background-color: black; border-image: url(%s); background-repeat: repeat-y;" %(Config.background)
# 6. same as 2
frame1_style = "background-color: black; border-image: url(%s); background-repeat: repeat-x;" %(Config.background)
# 7. nope
frame1_style = "background-color: black; border-image: url(%s); background-size: contain;" %(Config.background)
# 8. same as 2 - if image aspect matches height-width, then all is well
frame1_style = "background-color: black; border-image: url(%s);" %(Config.background)

frame1.setStyleSheet("#frame1 {%s}" %(frame1_style))
frames.append(frame1)

frame2 = QtGui.QFrame(w)
frame2.setObjectName("frame2")
frame2.setGeometry(0, 0, width, height)
frame2.setStyleSheet("#frame2 { background-color: blue; border-image: url(" +
                     Config.background + ") 0 0 0 0 repeat repeat;}")
frame2.setVisible(False)
frames.append(frame2)

# frame3 = QtGui.QFrame(w)
# frame3.setObjectName("frame3")
# frame3.setGeometry(0,0,width,height)
# frame3.setStyleSheet("#frame3 { background-color: blue; border-image:
#       url("+Config.background+") 0 0 0 0 stretch stretch;}")
# frame3.setVisible(False)
# frames.append(frame3)

# GDN: this draws borders around the two radar maps
bShowBothRadar = False
if bShowBothRadar:
    squares1 = QtGui.QFrame(frame1)
    squares1.setObjectName("squares1")
    squares1.setGeometry(0, height - yscale * 600, xscale * 340, yscale * 600)
    squares1.setStyleSheet(
        "#squares1 { background-color: transparent; border-image: url(" +
        Config.squares1 + ") 0 0 0 0 stretch stretch;}")
else:
    pass
    # GDN: absolutely don't need "squares1" QFrame. Instead just draw a border
    # around the object that is the Radar display.
    # Or I guess we could put the Radar inside "squares1"
    '''
    # It's a green frame
    squares1 = QtGui.QFrame(frame1)
    squares1.setObjectName("squares1")
    squares1.setGeometry(0, height - yscale * 282, xscale * 310, yscale * 282)
    squares1.setStyleSheet(
        "#squares1 { background-color: transparent; border:3px solid rgb(0, 255, 0);}")
    '''

# GDN: this draws frame around all the forecast boxes
squares2 = QtGui.QFrame(frame1)
squares2.setObjectName("squares2")
# GDN: why 340? Later when the labels "lab" are created, the value of 300 is used
squares2.setGeometry(width - xscale * 340, 0, xscale * 340, yscale * vHeight)
if False:
    squares2.setStyleSheet(
        "#squares2 { background-color: transparent; border-image: url(" +
        Config.squares2 +
        ") 0 0 0 0 stretch stretch;}")
else:
    # It's a green frame
    squares2.setStyleSheet(
        "#squares2 { background-color: transparent; border:3px solid rgb(0, 255, 0);}")

if not Config.digital:
    clockface = QtGui.QFrame(frame1)
    clockface.setObjectName("clockface")
    clockrect = QtCore.QRect(
        width / 2 - height * .4,
        height * .45 - height * .4,
        height * .8,
        height * .8)
    clockface.setGeometry(clockrect)
    clockface.setStyleSheet(
        "#clockface { background-color: transparent; border-image: url(" +
        Config.clockface +
        ") 0 0 0 0 stretch stretch;}")

    hourhand = QtGui.QLabel(frame1)
    hourhand.setObjectName("hourhand")
    hourhand.setStyleSheet("#hourhand { background-color: transparent; }")

    minhand = QtGui.QLabel(frame1)
    minhand.setObjectName("minhand")
    minhand.setStyleSheet("#minhand { background-color: transparent; }")

    sechand = QtGui.QLabel(frame1)
    sechand.setObjectName("sechand")
    sechand.setStyleSheet("#sechand { background-color: transparent; }")

    hourpixmap = QtGui.QPixmap(Config.hourhand)
    hourpixmap2 = QtGui.QPixmap(Config.hourhand)
    minpixmap = QtGui.QPixmap(Config.minhand)
    minpixmap2 = QtGui.QPixmap(Config.minhand)
    secpixmap = QtGui.QPixmap(Config.sechand)
    secpixmap2 = QtGui.QPixmap(Config.sechand)
else:
    clockface = QtGui.QLabel(frame1)
    clockface.setObjectName("clockface")
    clockrect = QtCore.QRect(
        width / 2 - height * .4,
        height * .45 - height * .4,
        height * .8,
        height * .8)
    clockface.setGeometry(clockrect)
    dcolor = QColor(Config.digitalcolor).darker(0).name()
    lcolor = QColor(Config.digitalcolor).lighter(120).name()
    clockface.setStyleSheet(
        "#clockface { background-color: transparent; font-family:sans-serif;" +
        " font-weight: light; color: " +
        lcolor +
        "; background-color: transparent; font-size: " +
        str(int(Config.digitalsize * xscale)) +
        "px; " +
        Config.fontattr +
        "}")
    clockface.setAlignment(Qt.AlignCenter)
    clockface.setGeometry(clockrect)
    glow = QtGui.QGraphicsDropShadowEffect()
    glow.setOffset(0)
    glow.setBlurRadius(50)
    glow.setColor(QColor(dcolor))
    clockface.setGraphicsEffect(glow)


# GDN: next two are radar displays in lower left that are vertically stacked
# They are contained within frame1
# This is regional display:
radar1rect = QtCore.QRect(3 * xscale, 622 * yscale, 300 * xscale, 275 * yscale)
objradar1 = Radar(frame1, Config.radar1, radar1rect, "radar1")
objradar2 = None
if bShowBothRadar:
    # This is local display:
    radar2rect = QtCore.QRect(3 * xscale, 344 * yscale, 300 * xscale, 275 * yscale)
    objradar2 = Radar(frame1, Config.radar2, radar2rect, "radar2")

# GDN: next two are radar displays that occupy most of screen and are side-by-side
# They are contained within frame2
radar3rect = QtCore.QRect(13 * xscale, 50 * yscale, 700 * xscale, 700 * yscale)
objradar3 = Radar(frame2, Config.radar3, radar3rect, "radar3")

radar4rect = QtCore.QRect(726 * xscale, 50 * yscale,700 * xscale, 700 * yscale)
objradar4 = Radar(frame2, Config.radar4, radar4rect, "radar4")

# Create the panels that display current obs in either frame1 or frame2
currObsDispSmall = CurrentObsDisp(frame1,bSmall=True)
currObsDispBig   = CurrentObsDisp(frame2,bSmall=False)

# TODO: should not have to do this
datex = currObsDispSmall.datex
datex2 = currObsDispBig.datex2
datey2 = currObsDispBig.datey2

# This is for display of sunrise and sunset
bottom = QtGui.QLabel(frame1)
bottom.setObjectName("bottom")
bottom.setStyleSheet("#bottom { font-family:sans-serif; color: " +
                     Config.textcolor +
                     "; background-color: transparent; font-size: " +
                     str(int(40 * xscale)) +
                     "px; " +
                     Config.fontattr +
                     "}")
bottom.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
bottom.setGeometry(0, height - 50, width, 50)

# This is display of your household temperature from a network connection
tempHouse = QtGui.QLabel(frame1)
tempHouse.setObjectName("temp")
tempHouse.setStyleSheet("#temp { font-family:sans-serif; color: " +
                   Config.textcolor +
                   "; background-color: transparent; font-size: " +
                   str(int(50 * xscale)) +
                   "px; " +
                   Config.fontattr +
                   "}")
tempHouse.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
tempHouse.setGeometry(0, height - 80, width, 50)

# Create array of boxes to display hourly and daily forecasts.
# But the boxes are just placeholders for dynamically updated forecasts.
forecast = []
n_forecast = numHourly+numDaily
ht_forecast = float(vHeight) / n_forecast
for i in range(0, numHourly+numDaily):
    lab = FcstDisp(frame1,i)
    forecast.append(lab)

manager = QtNetwork.QNetworkAccessManager()

# proxy = QNetworkProxy()
# proxy.setType(QNetworkProxy.HttpProxy)
# proxy.setHostName("localhost")
# proxy.setPort(8888)
# QNetworkProxy.setApplicationProxy(proxy)

stimer = QtCore.QTimer()
stimer.singleShot(10, qtstart)

# print radarurl(Config.radar1,radar1rect)

w.show()
if Config.bFullScreen:     # GDN
    w.showFullScreen()

#sys.exit(app.exec_())
exit(app.exec_())
