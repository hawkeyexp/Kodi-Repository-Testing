#!/usr/bin/env python
# -*- coding: utf-8 -*-
from BeautifulSoup import BeautifulStoneSoup
from common import *
import subprocess
import threading
import codecs
import shlex

platform = 0
osWindows = 1
osLinux = 2
osOSX = 3
osAndroid = 4
if xbmc.getCondVisibility('system.platform.windows'):
    platform = osWindows
if xbmc.getCondVisibility('system.platform.linux'):
    platform = osLinux
if xbmc.getCondVisibility('system.platform.osx'):
    platform = osOSX
if xbmc.getCondVisibility('system.platform.android'):
    platform = osAndroid

osLE = socket.gethostname() == 'LibreELEC'
hasExtRC = xbmc.getCondVisibility('System.HasAddon(script.chromium_remotecontrol)')
useIntRC = addon.getSetting("remotectrl") == 'true'
browser = int(addon.getSetting("browser"))
RMC_vol = addon.getSetting("remote_vol") == 'true'


def PLAYVIDEO():
    amazonUrl = BASE_URL + "/dp/" + args.get('asin')
    trailer = args.get('trailer') == '1'
    isAdult = args.get('adult') == '1'
    playable = False
    fallback = int(addon.getSetting("fallback_method"))
    methodOW = fallback - 1 if args.get('forcefb') and fallback else playMethod
    videoUrl = "%s/?autoplay%s=1" % (amazonUrl, ('trailer' if trailer == '1' else ''))
    extern = not xbmc.getInfoLabel('Container.PluginName').startswith('plugin.video.amazon')

    if extern:
        Log('External Call', xbmc.LOGDEBUG)

    while not playable:
        playable = True

        if methodOW == 2 and platform == osAndroid:
            AndroidPlayback(args.get('asin'), trailer)
        elif methodOW == 3:
            playable = IStreamPlayback(trailer, isAdult, extern)
        elif platform != osAndroid:
            ExtPlayback(videoUrl, isAdult, methodOW)

        if not playable:
            if fallback:
                methodOW = fallback - 1
            else:
                xbmc.sleep(500)
                Dialog.ok(getString(30203), getString(30218))
                playable = True

    if methodOW !=3:
        playDummyVid()


def ExtPlayback(videoUrl, isAdult, method):
    waitsec = int(addon.getSetting("clickwait")) * 1000
    pin = addon.getSetting("pin")
    waitpin = int(addon.getSetting("waitpin")) * 1000
    waitprepin = int(addon.getSetting("waitprepin")) * 1000
    pininput = addon.getSetting("pininput") == 'true'
    fullscr = addon.getSetting("fullscreen") == 'true'
    videoUrl += '&playerDebug=true' if verbLog else ''

    xbmc.Player().stop()
    xbmc.executebuiltin('ActivateWindow(busydialog)')
    suc, url = getCmdLine(videoUrl, method)
    if not suc:
        Dialog.notification(getString(30203), url, xbmcgui.NOTIFICATION_ERROR)
        return

    Log('Executing: %s' % url)
    if platform == osWindows:
        process = subprocess.Popen(url, startupinfo=getStartupInfo())
    else:
        param = shlex.split(url)
        process = subprocess.Popen(param)
        if osLE:
            result = 1
            while result != 0:
                p = subprocess.Popen('pgrep chrome > /dev/null', shell=True)
                p.wait()
                result = p.returncode

    if isAdult and pininput:
        if fullscr:
            waitsec *= 0.75
        else:
            waitsec = waitprepin
        xbmc.sleep(int(waitsec))
        Input(keys=pin)
        waitsec = waitpin

    if fullscr:
        xbmc.sleep(int(waitsec))
        if browser != 0:
            Input(keys='f')
        else:
            Input(mousex=-1, mousey=350, click=2)
            xbmc.sleep(500)
            Input(mousex=9999, mousey=350)

    Input(mousex=9999, mousey=-1)

    xbmc.executebuiltin('Dialog.Close(busydialog)')
    if hasExtRC:
        return

    myWindow = window(process)
    myWindow.wait()


def AndroidPlayback(asin, trailer):
    manu = ''
    if os.access('/system/bin/getprop', os.X_OK):
        manu = check_output(['getprop', 'ro.product.manufacturer'])

    if manu == 'Amazon':
        pkg = 'com.fivecent.amazonvideowrapper'
        act = ''
        url = asin
    else:
        pkg = 'com.amazon.avod.thirdpartyclient'
        act = 'android.intent.action.VIEW'
        url = BASE_URL + '/piv-apk-play?asin=' + asin
        if trailer:
            url += '&playTrailer=T'
    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Manufacturer: ' + manu])
    subprocess.Popen(['log', '-p', 'v', '-t', 'Kodi-Amazon', 'Starting App: %s Video: %s' % (pkg, url)])
    Log('Manufacturer: %s' % manu)
    Log('Starting App: %s Video: %s' % (pkg, url))
    if verbLog:
        if os.access('/system/xbin/su', os.X_OK) or os.access('/system/bin/su', os.X_OK):
            Log('Logcat:\n' + check_output(['su', '-c', 'logcat -d | grep -i com.amazon.avod']))
        Log('Properties:\n' + check_output(['sh', '-c', 'getprop | grep -iE "(ro.product|ro.build|google)"']))
    xbmc.executebuiltin('StartAndroidActivity("%s", "%s", "", "%s")' % (pkg, act, url))


def check_output(*popenargs, **kwargs):
    p = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)
    out, err = p.communicate()
    retcode = p.poll()
    if retcode != 0:
        c = kwargs.get('args')
        if c is None:
            c = popenargs[0]
            e = subprocess.CalledProcessError(retcode, c)
            e.output = str(out) + str(err)
            Log(e, xbmc.LOGERROR)
    return out.strip()


def IStreamPlayback(trailer, isAdult, extern):
    if not is_addon:
        Log('No Inputstream Addon found or activated')
        Dialog.notification(getString(30203), 'No Inputstream Addon found or activated', xbmcgui.NOTIFICATION_ERROR)
        return True

    values = getFlashVars()
    if not values:
        return True

    vMT = 'Trailer' if trailer else 'Feature'

    mpd, subs = getStreams(*getUrldata('catalog/GetPlaybackResources', values, extra=True, vMT=vMT,
                                       opt='&titleDecorationScheme=primary-content'), retmpd=True)

    licURL = getUrldata('catalog/GetPlaybackResources', values, extra=True, vMT=vMT, dRes='Widevine2License', retURL=True)

    if not mpd:
        Dialog.notification(getString(30203), subs, xbmcgui.NOTIFICATION_ERROR)
        return True

    orgmpd = mpd
    is_version = xbmcaddon.Addon(is_addon).getAddonInfo('version') if is_addon else '0'
    mpd = re.sub(r'~', '', mpd) if mpd != re.sub(r'~', '', mpd) else re.sub(r'/[1-9][$].*?/', '/', mpd)

    if addon.getSetting("drm_check") == 'true':
        mpdcontent = getURL(mpd, retjson=False)
        if len(re.compile(r'(?i)edef8ba9-79d6-4ace-a3c8-27dcd51d21ed').findall(mpdcontent)) < 2:
            if platform != osAndroid and int(is_version[0:1]) < 2:
                xbmc.executebuiltin('ActivateWindow(busydialog)')
                return False
        elif platform == osAndroid or int(is_version[0:1]) >= 2:
            mpd = orgmpd

    Log(mpd)

    infoLabels = GetStreamInfo(args.get('asin'))
    mpaa_str = RestrAges + getString(30171)
    mpaa_check = infoLabels.get('MPAA', mpaa_str) in mpaa_str or isAdult
    if mpaa_check and not RequestPin():
        return True

    listitem = xbmcgui.ListItem(path=mpd)
    if extern:
        infoLabels['Title'] = infoLabels.get('EpisodeName', infoLabels['Title'])
    if trailer:
        infoLabels['Title'] += ' (Trailer)'
    if 'Thumb' not in infoLabels.keys():
        infoLabels['Thumb'] = None
    if 'Fanart' in infoLabels.keys():
        listitem.setArt({'fanart': infoLabels['Fanart']})
    if 'Poster' in infoLabels.keys():
        listitem.setArt({'tvshow.poster': infoLabels['Poster']})
    else:
        listitem.setArt({'poster': infoLabels['Thumb']})

    if 'adaptive' in is_addon:
        listitem.setProperty('inputstream.adaptive.manifest_type', 'mpd')

    Log('Using %s Version:%s' %(is_addon, is_version))
    listitem.setArt({'thumb': infoLabels['Thumb']})
    listitem.setInfo('video', infoLabels)
    listitem.setSubtitles(subs)
    listitem.setProperty('%s.license_type' % is_addon, 'com.widevine.alpha')
    listitem.setProperty('%s.license_key' % is_addon, licURL)
    listitem.setProperty('%s.stream_headers' % is_addon, 'user-agent=' + UserAgent)
    listitem.setProperty('inputstreamaddon', is_addon)
    xbmcplugin.setResolvedUrl(pluginhandle, True, listitem=listitem)

    while not xbmc.Player().isPlaying():
        xbmc.sleep(500)

    xbmc.sleep(5000)
    Log('Playback startet...', 0)
    Log('Video ContentType Movie? %s' % xbmc.getCondVisibility('VideoPlayer.Content(movies)'), 0)
    Log('Video ContentType Episode? %s' % xbmc.getCondVisibility('VideoPlayer.Content(episodes)'), 0)
    return True


def parseSubs(data):
    subs = []
    if addon.getSetting('subtitles') == 'false' or 'subtitleUrls' not in data:
        return subs

    for sub in data['subtitleUrls']:
        lang = sub['displayName'].split('(')[0].strip()
        Log('Convert %s Subtitle' % lang)
        srtfile = xbmc.translatePath('special://temp/%s.srt' % lang).decode('utf-8')
        srt = codecs.open(srtfile, 'w', encoding='utf-8')
        soup = BeautifulStoneSoup(getURL(sub['url'], retjson=False), convertEntities=BeautifulStoneSoup.XML_ENTITIES)
        enc = soup.originalEncoding
        num = 0
        for caption in soup.findAll('tt:p'):
            num += 1
            subtext = caption.renderContents().decode(enc).replace('<tt:br>', '\n').replace('</tt:br>', '')
            srt.write(u'%s\n%s --> %s\n%s\n\n' % (num, caption['begin'], caption['end'], subtext))
        srt.close()
        subs.append(srtfile)
    return subs


def GetStreamInfo(asin):
    import movies
    import listmovie
    import tv
    import listtv
    moviedata = movies.lookupMoviedb(asin)
    if moviedata:
        return listmovie.ADD_MOVIE_ITEM(moviedata, onlyinfo=True)
    else:
        epidata = tv.lookupTVdb(asin)
        if epidata:
            return listtv.ADD_EPISODE_ITEM(epidata, onlyinfo=True)
    return {'Title': ''}


def getCmdLine(videoUrl, method):
    scr_path = addon.getSetting("scr_path")
    br_path = addon.getSetting("br_path").strip()
    scr_param = addon.getSetting("scr_param").strip()
    kiosk = addon.getSetting("kiosk") == 'true'
    appdata = addon.getSetting("ownappdata") == 'true'
    cust_br = addon.getSetting("cust_path") == 'true'
    nobr_str = getString(30198)

    if method == 1:
        if not xbmcvfs.exists(scr_path):
            return False, nobr_str

        suc, fr = getPlaybackInfo()
        if not suc:
            return False, fr

        return True, scr_path + ' ' + scr_param.replace('{f}', fr).replace('{u}', videoUrl)

    os_paths = [None, ('C:\\Program Files\\', 'C:\\Program Files (x86)\\'), ('/usr/bin/', '/usr/local/bin/'), 'open -a ']
    # path(0,win,lin,osx), kiosk, profile, args

    br_config = [[(None, ['Internet Explorer\\iexplore.exe'], '', ''), '-k ', '', ''],
                 [(None, ['Google\\Chrome\\Application\\chrome.exe'],
                   ['google-chrome', 'google-chrome-stable', 'google-chrome-beta', 'chromium-browser'],
                   '"/Applications/Google Chrome.app"'),
                  '--kiosk ', '--user-data-dir=',
                  '--start-maximized --disable-translate --disable-new-tab-first-run --no-default-browser-check --no-first-run '],
                 [(None, ['Mozilla Firefox\\firefox.exe'], ['firefox'], 'firefox'), '', '-profile ', ''],
                 [(None, ['Safari\\Safari.exe'], '', 'safari'), '', '', '']]

    if not cust_br:
        br_path = ''

    if platform != osOSX and not cust_br:
        for path in os_paths[platform]:
            for brfile in br_config[browser][0][platform]:
                if xbmcvfs.exists(os.path.join(path, brfile)):
                    br_path = path + brfile
                    break
                else:
                    Log('Browser %s not found' % (path + brfile), xbmc.LOGDEBUG)
            if br_path:
                break

    if not xbmcvfs.exists(br_path) and platform != osOSX:
        return False, nobr_str

    br_args = br_config[browser][3]
    if kiosk:
        br_args += br_config[browser][1]

    if appdata and br_config[browser][2]:
        br_args += br_config[browser][2] + '"' + os.path.join(pldatapath, str(browser)) + '" '

    if platform == osOSX:
        if not cust_br:
            br_path = os_paths[osOSX] + br_config[browser][0][osOSX]

        if br_args.strip():
            br_args = '--args ' + br_args

    br_path += ' %s"%s"' % (br_args, videoUrl)

    return True, br_path


def getStartupInfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    return si


def getStreams(suc, data, retmpd=False):
    HostSet = addon.getSetting("pref_host")
    subUrls = []

    if not suc:
        return False, data

    if retmpd:
        subUrls = parseSubs(data)

    hosts = data['audioVideoUrls']['avCdnUrlSets']

    while hosts:
        for cdn in hosts:
            prefHost = False if HostSet not in str(hosts) or HostSet == 'Auto' else HostSet
            if prefHost and prefHost not in cdn['cdn']:
                continue
            Log('Using Host: ' + cdn['cdn'])

            for urlset in cdn['avUrlInfoList']:
                data = getURL(urlset['url'], retjson=False, check=retmpd)
                if not data:
                    hosts.remove(cdn)
                    Log('Host not reachable: ' + cdn['cdn'])
                    break
                if retmpd:
                    return urlset['url'], subUrls
                else:
                    fps_string = re.compile('frameRate="([^"]*)').findall(data)[0]
                    fr = round(eval(fps_string + '.0'), 3)
                    return True, str(fr).replace('.0', '')

    return False, getString(30217)


def getPlaybackInfo():
    if addon.getSetting("framerate") == 'false':
        return True, ''
    values = getFlashVars()
    if not values:
        return False, 'getFlashVars'
    suc, fr = getStreams(*getUrldata('catalog/GetPlaybackResources', values, extra=True))
    return suc, fr


def getFlashVars():
    cookie = mechanizeLogin()
    if not cookie:
        return False
    url = BASE_URL + '/gp/deal/ajax/getNotifierResources.html'
    showpage = getURL(url, useCookie=cookie)

    if not showpage:
        Dialog.notification(pluginname, Error({'errorCode': 'invalidrequest', 'message': 'getFlashVars'}),
                            xbmcgui.NOTIFICATION_ERROR)
        return False

    values = {'asin': args.get('asin'),
              'deviceTypeID': 'AOAGZA014O5RE',
              'userAgent': UserAgent}
    values.update(showpage['resourceData']['GBCustomerData'])

    if 'customerId' not in values:
        Dialog.notification(getString(30200), getString(30210), xbmcgui.NOTIFICATION_ERROR)
        return False

    values['deviceID'] = gen_id()
    rand = 'onWebToken_' + str(randint(0, 484))
    pltoken = getURL(BASE_URL + "/gp/video/streaming/player-token.json?callback=" + rand,
                     useCookie=cookie, retjson=False)
    try:
        values['token'] = re.compile('"([^"]*).*"([^"]*)"').findall(pltoken)[0][1]
    except IndexError:
        Dialog.notification(getString(30200), getString(30201), xbmcgui.NOTIFICATION_ERROR)
        return False
    return values


def getUrldata(mode, values, devicetypeid=False, version=1, firmware='1', opt='', extra=False,
               useCookie=False, retURL=False, vMT='Feature', dRes='AudioVideoUrls,SubtitleUrls'):
    if not devicetypeid:
        devicetypeid = values['deviceTypeID']
    url = ATV_URL + '/cdp/' + mode
    url += '?titleId=' + values['asin']
    url += '&deviceTypeID=' + devicetypeid
    url += '&firmware=' + firmware
    url += '&customerID=' + values['customerId']
    url += '&deviceID=' + values['deviceID']
    url += '&marketplaceID=' + values['marketplaceId']
    url += '&token=' + values['token']
    url += '&format=json'
    url += '&version=' + str(version)
    url += opt
    if extra:
        url += '&resourceUsage=ImmediateConsumption&consumptionType=Streaming&deviceDrmOverride=CENC' \
               '&deviceStreamingTechnologyOverride=DASH&deviceProtocolOverride=Http&audioTrackId=all' \
               '&deviceBitrateAdaptationsOverride=CVBR%2CCBR'
        url += '&videoMaterialType=' + vMT
        url += '&desiredResources=' + dRes
        url += '&supportedDRMKeyScheme=DUAL_KEY' if platform != osAndroid and 'AudioVideoUrls' in dRes else ''
    if retURL:
        return url
    data = getURL(url, useCookie=useCookie, retjson=False)
    if data:
        error = re.findall('{[^"]*"errorCode[^}]*}', data)
        if error:
            return False, Error(json.loads(error[0]))
        return True, json.loads(data)
    return False, 'HTTP Error'


def Error(data):
    code = data['errorCode'].lower()
    Log('%s (%s) ' % (data['message'], code), xbmc.LOGERROR)
    if 'invalidrequest' in code:
        return getString(30204)
    elif 'noavailablestreams' in code:
        return getString(30205)
    elif 'notowned' in code:
        return getString(30206)
    elif 'invalidgeoip' or 'dependency' in code:
        return getString(30207)
    elif 'temporarilyunavailable' in code:
        return getString(30208)
    else:
        return '%s (%s) ' % (data['message'], code)


def Input(mousex=0, mousey=0, click=0, keys=None, delay='200'):
    screenWidth = int(xbmc.getInfoLabel('System.ScreenWidth'))
    screenHeight = int(xbmc.getInfoLabel('System.ScreenHeight'))
    keys_only = sc_only = keybd = ''
    if mousex == -1:
        mousex = screenWidth / 2

    if mousey == -1:
        mousey = screenHeight / 2
    spec_keys = {'{EX}': ('!{F4}', 'control+shift+q', 'kd:cmd t:q ku:cmd'),
                 '{SPC}': ('{SPACE}', 'space', 't:p'),
                 '{LFT}': ('{LEFT}', 'Left', 'kp:arrow-left'),
                 '{RGT}': ('{RIGHT}', 'Right', 'kp:arrow-right'),
                 '{U}': ('{UP}', 'Up', 'kp:arrow-up'),
                 '{DWN}': ('{DOWN}', 'Down', 'kp:arrow-down'),
                 '{BACK}': ('{BS}', 'BackSpace', 'kp:delete'),
                 '{RET}': ('{ENTER}', 'Return', 'kp:return')}

    if keys:
        keys_only = keys
        for sc in spec_keys:
            while sc in keys:
                keys = keys.replace(sc, spec_keys[sc][platform - 1]).strip()
                keys_only = keys_only.replace(sc, '').strip()
        sc_only = keys.replace(keys_only, '').strip()

    if platform == osWindows:
        app = os.path.join(pluginpath, 'tools', 'userinput.exe')
        mouse = ' mouse %s %s' % (mousex, mousey)
        mclk = ' ' + str(click)
        keybd = ' key %s %s' % (keys, delay)
    elif platform == osLinux:
        app = 'xdotool'
        mouse = ' mousemove %s %s' % (mousex, mousey)
        mclk = ' click --repeat %s 1' % click
        if keys_only:
            keybd = ' type --delay %s %s' % (delay, keys_only)

        if sc_only:
            if keybd:
                keybd += ' && ' + app

            keybd += ' key ' + sc_only
    elif platform == osOSX:
        app = 'cliclick'
        mouse = ' m:'
        if click == 1:
            mouse = ' c:'
        elif click == 2:
            mouse = ' dc:'
        mouse += '%s,%s' % (mousex, mousey)
        mclk = ''
        keybd = ' -w %s' % delay
        if keys_only:
            keybd += ' t:%s' % keys_only

        if keys != keys_only:
            keybd += ' ' + sc_only
    if keys:
        cmd = app + keybd
    else:
        cmd = app + mouse
        if click:
            cmd += mclk

    Log('Run command: %s' % cmd)
    rcode = subprocess.call(cmd, shell=True)
    if rcode:
        Log('Returncode: %s' % rcode)


def playDummyVid():
    dummy_video = os.path.join(pluginpath, 'resources', 'dummy.avi')
    xbmcplugin.setResolvedUrl(pluginhandle, True, xbmcgui.ListItem(path=dummy_video))
    Log('Playing Dummy Video', xbmc.LOGDEBUG)
    xbmc.Player().stop()
    return


def SetVol(step):
    rpc = '{"jsonrpc": "2.0", "method": "Application.GetProperties", "params": {"properties": ["volume"]}, "id": 1}'
    vol = json.loads(xbmc.executeJSONRPC(rpc))["result"]["volume"]
    xbmc.executebuiltin('SetVolume(%d,showVolumeBar)' % (vol + step))


class window(xbmcgui.WindowDialog):
    def __init__(self, process):
        xbmcgui.WindowDialog.__init__(self)
        self._stopEvent = threading.Event()
        self._pbStart = time.time()
        self._wakeUpThread = threading.Thread(target=self._wakeUpThreadProc, args=(process,))
        self._vidDur = self.getDuration()

    def _wakeUpThreadProc(self, process):
        starttime = time.time()
        while not self._stopEvent.is_set():
            if time.time() > starttime + 60:
                starttime = time.time()
                xbmc.executebuiltin("playercontrol(wakeup)")
            if process:
                process.poll()
                if process.returncode is not None:
                    self.close()

            self._stopEvent.wait(1)

    def wait(self):
        Log('Starting Thread')
        self._wakeUpThread.start()
        self.doModal()
        self._wakeUpThread.join()

    @staticmethod
    def getDuration():
        if xbmc.getInfoLabel('ListItem.Duration'):
            return int(xbmc.getInfoLabel('ListItem.Duration')) * 60
        else:
            infoLabels = GetStreamInfo(args.get('asin'))
            return int(infoLabels.get('Duration', 0))

    def close(self):
        Log('Stopping Thread')
        self._stopEvent.set()
        xbmcgui.WindowDialog.close(self)
        watched = xbmc.getInfoLabel('Listitem.PlayCount')
        pBTime = time.time() - self._pbStart
        Log('Dur:%s State:%s PlbTm:%s' % (self._vidDur, watched, pBTime), xbmc.LOGDEBUG)

        if pBTime > self._vidDur * 0.9 and not watched:
            xbmc.executebuiltin("Action(ToggleWatched)")

    def onAction(self, action):
        if not useIntRC:
            return

        ACTION_SELECT_ITEM = 7
        ACTION_PARENT_DIR = 9
        ACTION_PREVIOUS_MENU = 10
        ACTION_PAUSE = 12
        ACTION_STOP = 13
        ACTION_SHOW_INFO = 11
        ACTION_SHOW_GUI = 18
        ACTION_MOVE_LEFT = 1
        ACTION_MOVE_RIGHT = 2
        ACTION_MOVE_UP = 3
        ACTION_MOVE_DOWN = 4
        ACTION_PLAYER_PLAY = 79
        ACTION_VOLUME_UP = 88
        ACTION_VOLUME_DOWN = 89
        ACTION_MUTE = 91
        ACTION_NAV_BACK = 92
        ACTION_BUILT_IN_FUNCTION = 122
        KEY_BUTTON_BACK = 275
        ACTION_BACKSPACE = 110
        ACTION_MOUSE_MOVE = 107

        actionId = action.getId()
        showinfo = action == ACTION_SHOW_INFO
        Log('Action: Id:%s ButtonCode:%s' % (actionId, action.getButtonCode()))

        if action in [ACTION_SHOW_GUI, ACTION_STOP, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK,
                      KEY_BUTTON_BACK, ACTION_MOUSE_MOVE]:
            Input(keys='{EX}')
        elif action in [ACTION_SELECT_ITEM, ACTION_PLAYER_PLAY, ACTION_PAUSE]:
            Input(keys='{SPC}')
            showinfo = True
        elif action == ACTION_MOVE_LEFT:
            Input(keys='{LFT}')
            showinfo = True
        elif action == ACTION_MOVE_RIGHT:
            Input(keys='{RGT}')
            showinfo = True
        elif action == ACTION_MOVE_UP:
            SetVol(+2) if RMC_vol else Input(keys='{U}')
        elif action == ACTION_MOVE_DOWN:
            SetVol(-2) if RMC_vol else Input(keys='{DWN}')
        # numkeys for pin input
        elif 57 < actionId < 68:
            strKey = str(actionId - 58)
            Input(keys=strKey)

        if showinfo:
            Input(9999, 0)
            xbmc.sleep(500)
            Input(9999, -1)
