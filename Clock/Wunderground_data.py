
class WundergroundData:
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
                data = wxdata[key[1]]
            if key[2] == -1 or key[2] == Config.metric:
                # Config.metric has value of either 0 or 1
                self.obs[key[0]] = [data,key[3]]
            else:
                # key[2] != Config.metric, so skip this obs
                pass
                
        # Special case for 'icon', because we have local copies
        iconurl = wxdata['icon_url']
        icp = ''
        if not daily and re.search('/nt_', iconurl):
            icp = 'n_'
        self.obs['icon'] = [Config.icons + "/" + icp + wxdata['icon'] + ".png",'']
                
    def getObsStr(self,key):
        # Get value from wxdata + the appropriate units string
        return str(self.obs[key][0]) + self.obs[key][1]
        
class CurrentObs(WundergroundData):
    # Lookup table for key used in application display,
    # key used in wxdata returned by wunderground,
    # metric=1 or English=0 units or no_units=-1
    # and displays units (if any) in the application
    obsKeys = [
        # app key,  data key,   metric, units
        ('icon',                'icon',                -1,      ''),
        ('wx_text',             'weather',             -1,      ''),
        ('press_trend',         'pressure_trend',      -1,      ''),
        ('rel_hum',             'relative_humidity',   -1,      ''),
        ('wind_dir',            'wind_dir',            -1,      ''),
        ('wind_degrees',        'wind_degrees',        -1,      ''),
        ('local_epoch',         'local_epoch',         -1,      ''),
        ('temp',                'temp_c',               1,      u'°C'),
        ('temp',                'temp_f',               0,      u'°F'),
        ('press',               'pressure_mb',          1,      'mm'),
        ('press',               'pressure_in',          0,      'in'),
        ('temp_feels_like',     'feelslike_c',          1,      u'°C'),
        ('temp_feels_like',     'feelslike_f',          0,      u'°F'),
        ('wind_speed',          'wind_kph',             1,      ''),
        ('wind_speed',          'wind_mph',             0,      ''),
        ('wind_gust',           'wind_gust_kph',        1,      ''),
        ('wind_gust',           'wind_gust_mph',        0,      ''),
        ('precip_1hr',          'precip_1hr_metric',    1,      'mm'),
        ('precip_today',        'precip_today_metric',  1,      'mm'),
        ('precip_1hr',          'precip_1hr_in',        0,      'in'),
        ('precip_today',        'precip_today_in',      0,      'in'),
    ]
    def __init__(self,wxdata):
        WundergroundData.__init__(self,wxdata,self.obsKeys,daily=False)

class FcstDailyData(WundergroundData):
    # Lookup table for key used in application display,
    # key used in wxdata returned by wunderground,
    # metric=1 or English=0 units,
    # and displays units (if any) in the application
    obsKeys = [
        # app key,  data key,   metric, units
        ('icon',                'icon',                -1,      ''),
        ('wx_text',             'conditions',          -1,      ''),
        ('day',                 ['date','weekday_short'],-1,      ''),
        ('temp_high',           ['high','celsius'],     1,      u'°C'),
        ('temp_low',            ['low','celsius'],      1,      u'°C'),
        ('temp_high',           ['high','fahrenheit'],  0,      u'°F'),
        ('temp_low',            ['low','fahrenheit'],   0,      u'°F'),
        ('pop',                 'pop',                 -1,      '%'),
        ('qpf',                 ['qpf_allday','mm'],    1,      'mm'),
        ('qpf',                 ['qpf_allday','in'],    0,      'in'),
        ('snow',                ['snow_allday','cm'],   1,      'mm'),
        ('snow',                ['snow_allday','in'],   0,      'in'),
    ]
    def __init__(self,wxdata):
        WundergroundData.__init__(self,wxdata,self.obsKeys,daily=True)

class FcstHourlyData(WundergroundData):
    # Lookup table for key used in application display,
    # key used in wxdata returned by wunderground,
    # metric=1 or English=0 units,
    # and displays units (if any) in the application
    obsKeys = [
        # app key,  data key,   metric, units
        ('icon',                'icon',                -1,      ''),
        ('wx_text',             'condition',           -1,      ''),
        ('day',                 ['FCTTIME','weekday_name_abbrev'],             -1,      ''),
        ('hour',                ['FCTTIME','civil'],   -1,      ''),
        ('temp',                ['temp','metric'],      1,      u'°C'),
        ('temp',                ['temp','english'],     0,      u'°F'),
        ('pop',                 'pop',                 -1,      '%'),
        ('qpf',                 ['qpf','metric'],       1,      'mm'),
        ('qpf',                 ['qpf','english'],      0,      'in'),
        ('snow',                ['snow','metric'],      1,      'mm'),
        ('snow',                ['snow','english'],     0,      'in'),
    ]
    def __init__(self,wxdata):
        WundergroundData.__init__(self,wxdata,self.obsKeys,daily=False)
