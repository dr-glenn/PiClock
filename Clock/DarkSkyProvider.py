# -*- coding: utf-8 -*-                 # NOQA
# DarkSky forecast data https://api.darksky.net/forecast/b2d7cffe68190165c896172ddcec98c9/37.8267,-122.4233
# It returns current forecast for the next week
# This page describes the values returned: https://darksky.net/dev/docs#api-request-types
# Or just look at this page for an example: https://darksky.net/dev/docs

from PyQt4 import QtNetwork
#from PyQt4.QtGui import QPixmap, QMovie, QBrush, QColor, QPainter
from PyQt4.QtCore import QUrl
#from PyQt4.QtCore import Qt
from PyQt4.QtNetwork import QNetworkReply
from PyQt4.QtNetwork import QNetworkRequest
#from subprocess import Popen
import urllib2
import json

import Config
import ApiKeys
import logging
logger = logging.getLogger(__name__)

'''
DarkSky defines some strings to describe weather icons,
See page for more info: https://darksky.net/dev/docs#data-point-object
'''
# Here is a list of names, with mapping to icons stored locally
icon_names = {
'clear-day':            'clear.png',
'clear-night':          'n_clear.png',
'rain':                 'rain.png',
'snow':                 'snow.png',
'sleet':                'sleet.png',
'wind':                 '',
'fog':                  'fog.png',
'cloudy':               'cloudy.png',
'partly-cloudy-day':    'partlycloudy.png',
'partly-cloudy-night':  'n_partlycloudy.png',
}

class WxData:
    def __init__(self):
        self.wxdata = None
        self.wxurl = Config.darkPrefix + ApiKeys.darksky_key
        self.wxurl += '/' + str(Config.primary_coordinates[0]) + ',' + str(Config.primary_coordinates[1])
        self.wxurl += '?exclude=minutely&units=us'
        logger.debug('wxurl='+self.wxurl)
        self.hasData = False
    def getwx(self):
        self.hasData = False
        if False:
            r = QUrl(self.wxurl)
            r = QNetworkRequest(r)
            self.manager = QtNetwork.QNetworkAccessManager()
            self.wxreply = self.manager.get(r)
            self.wxreply.finished.connect(self.wxfinished)
        else:
            self.wxreply = urllib2.urlopen(self.wxurl)
            wxstr = self.wxreply.read()
            logger.debug('wxstr: %s' %(wxstr[:200]))
            self.wxdata = json.loads(wxstr)
            self.hasData = True
    def wxfinished(self):
        wxstr = str(self.wxreply.readAll())
        if not wxstr:
            logger.warning('wxstr is None')
            return
        self.wxdata = json.loads(wxstr)
        self.hasData = True
    def getData(self):
        if self.hasData:
            return self.wxdata
        else:
            return None
        
class DataParse:
    '''
    Abstract Class.
    Child classes: CurrentObs, FcstHourlyData, FcstDailyData.
    Parses JSON returned from Wunderground according to a list of keys.
    We request current observations and hourly and daily forecasts.
    Each of these items contains different sets of data with different keys.
    Once the data is parsed, the application can then request that the
    data be returned as a string, ready for display.
    '''
    def __init__(self,wxdata,dataKeys,daily=False):
        self.daily = daily
        self.obs = {}
        for key in dataKeys:
            if isinstance(key[1],(list,tuple)):
                try:
                    kk = key[1]
                    data = wxdata[kk[0]][kk[1]]
                except:
                    logger.error('key=%s, wxdata=%s' %(str(kk),str(wxdata[kk[0]])))
            else:
                if key[1] in wxdata:
                    data = wxdata[key[1]]
                    logger.debug('key=%s, data=%s' %(key[1],str(data)))
                else:
                    # DarkSky has optional fields, so it's OK if key[1] not found
                    logger.info('DataParse: key=%s not present in wxdata' %(key[1]))
                    continue
            if key[2] == -1 or key[2] == Config.metric:
                # Config.metric has value of either 0 or 1
                self.obs[key[0]] = [data,key[3]]
                logger.debug('save obs: key=%s, value=%s' %(key[0],str(self.obs[key[0]])))
            else:
                # key[2] != Config.metric, so skip this obs
                pass
                
        # Special case for 'icon', because we have local copies
        #iconurl = wxdata['icon_url']
        if wxdata['icon'] in icon_names:
            icon_png = icon_names[wxdata['icon']]
            self.obs['icon'] = [Config.icons + "/" + icon_png,'']
                
    def getObsStr(self,key):
        # Get value from wxdata + the appropriate units string
        if key in self.obs:
            # TODO: the obs tables should have a conversion function
            try:
                obsVal = float(self.obs[key][0])
                if abs(obsVal) >= 10.0:
                    obsVal = int(obsVal + 0.5)  # get rid of decimal places
                else:
                    obsVal = float('%.1f' %(obsVal))
            except:
                # could not convert to float, so assume it's a string
                obsVal = self.obs[key][0]
            if self.obs[key][1] == '%':
                retval = str(int(100.0 * obsVal + 0.5)) + self.obs[key][1]
            else:
                retval = str(obsVal) + self.obs[key][1]
            return retval
        else:
            logger.warning('key=%s not found' %(key))
            return None
        
class CurrentObs(DataParse):
    # Lookup table for key used in application display,
    # key used in wxdata returned by wunderground,
    # metric=1 or English=0 units or no_units=-1
    # and displays units (if any) in the application
    # NOTE: must use 'currently' node to fetch these
    obsKeys = [
        # app key,              data key,               metric, units
        ('icon',                'icon',                -1,      ''),
        ('wx_text',             'summary',             -1,      ''),
        ('rel_hum',             'humidity',   -1,      '%'),
        ('wind_degrees',        'windBearing',        -1,      ''),
        ('local_epoch',         'time',         -1,      ''),
        ('temp',                'temperature',               0,      u'°F'),
        ('press',               'pressure',          0,      'mb'),
        ('temp_feels_like',     'apparentTemperature',          0,      u'°F'),
        ('wind_speed',          'windSpeed',             0,      ''),
        ('wind_gust',           'windGust',        0,      ''),
        ('precip_1hr',          'precipIntensity',        0,      'in'),
    ]
    # other keys: precipProbability, precipType, dewPoint, cloudCover, uvIndex, visibility, ozone
    def __init__(self,wxdata):
        DataParse.__init__(self,wxdata['currently'],self.obsKeys,daily=False)

class FcstDailyData(DataParse):
    # Lookup table for key used in application display,
    # key used in wxdata returned by wunderground,
    # metric=1 or English=0 units,
    # and displays units (if any) in the application
    # NOTE: must use 'daily/data' node to fetch these
    obsKeys = [
        # app key,  data key,   metric, units
        ('icon',                'icon',                -1,      ''),
        ('wx_text',             'summary',          -1,      ''),
        ('day',                 'time',-1,      ''),
        ('temp_high',           'temperatureHigh',  0,      u'°F'),
        ('temp_low',            'temperatureLow',   0,      u'°F'),
        ('pop',                 'precipProbability',                 -1,      '%'),
        ('qpf',                 'precipIntensity',    0,      'in'),
        ('snow',                'precipAccumulation',  0,      'in'),
    ]
    # other keys: sunriseTime, sunsetTime, moonPhase, precipIntensityMax, precipIntensityMaxTime, more
    def __init__(self,wxdata,iday):
        DataParse.__init__(self,wxdata['daily']['data'][iday],self.obsKeys,daily=True)

class FcstHourlyData(DataParse):
    # Lookup table for key used in application display,
    # key used in wxdata returned by wunderground,
    # metric=1 or English=0 units,
    # and displays units (if any) in the application
    # NOTE: must use 'hourly/data' node to fetch these
    obsKeys = [
        # app key,  data key,   metric, units
        ('icon',                'icon',                -1,      ''),
        ('wx_text',             'summary',           -1,      ''),
        ('hour',                'time',   -1,      ''),
        ('temp',                'temperature',     0,      u'°F'),
        ('pop',                 'precipProbability',                 -1,      '%'),
        ('qpf',                 'precipIntensity',      0,      'in'),
        ('snow',                'precipAccumulation',  0,      'in'),
    ]
    # other keys: apparentTemperature, dewPoint, humidity, pressure, windSpeed, windGust, windBearing, cloudCover, uvIndex, visibility, ozone
    def __init__(self,wxdata,ihour):
        DataParse.__init__(self,wxdata['hourly']['data'][ihour],self.obsKeys,daily=False)
