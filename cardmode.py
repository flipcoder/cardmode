#!/usr/bin/python2
"""Card Mode
MIT License
Copyright (c) 2017 Grady O'Connell

WARNING: THIS HAS JUST STARTED DEVELOPMENT.
SINCE IT INVOLVES MERGING, SYNCING, AND OTHER POTENTIALLY DESTRUCTIVE OPERATIONS,
IT IS CURRENTLY UNSAFE FOR ALL PURPOSES.
TESTERS SHOULD USE AN ISOLATED ENVIRONMENT AND A SEPARATE ACCOUNT FOR
ALL CONNECTED SERVICES.  ALWAYS BACK UP BOTH ONLINE AND OFFLINE DATA!

Usage:
    cardmode.py [-hvso] [-s SERVICE] [-b BOARD] [ACTION ...]

Examples:
    cardmode.py                     show this
    cardmode.py --all               sync all boards for all services
    cardmode.py Tasks               sync 'Tasks' board to 'Tasks.cardmode' file
    cardmode.py Tasks.cardmode      same as above
    cardmode.py -b Tasks            same as above, more specific (*)
    cardmode.py -f Tasks.cardmode   same as above, more specific (*)
    cardmode.py -s trello Tasks     sync 'Tasks' board from Trello
    cardmode.py -b a -f a.cardmode  sync 'a' board w/ 'a.cardmode' file

Options:
    -h --help               show this
    -v --version            show version
    -s --service=<service>  service name [default: trello]
    -b --board=<board>      board name (*)
    -f --filename=<fn>      filename (*)
    -e --edit               open in editor
    -p --pull               pull in new changes
    -u --push               pushes, prompts on any updates
    --sync                  pushes, prompts on card updates only
    --reset                 pull, overwriting your local changes
    --all                   apply command to all boards on all services
    --close                 close a board
    -n --new                make a new board based on given filename

Ambiguity [*]:
    If you're using this in a script, use parameters (-sbf) instead of ACTION
    to resolve any ambiguity.

How does syncing work?
    Syncing will pull the board contents into a cardmode file for you to edit.
    If you have modified the cardmode file since last sync, it will merge the
    new changes into your file.
"""
from __future__ import unicode_literals, print_function
import os, sys, six, requests, json
import six.moves.configparser as configparser
from six.moves.configparser import ConfigParser,RawConfigParser
import appdirs
from collections import OrderedDict
from docopt import docopt
import json_delta

args = docopt(__doc__)

indent = 0
tout=None
tsrc=[]
def tindent(i=1):
    global indent
    indent += i
def toutdent(i=1):
    global indent
    indent -= i
def tprint(lines=''):
    lines = ''.join(lines).split('\n')
    r = []
    for line in lines:
        # TODO: escape this stuff
        print(' '*4*indent + unicode(line))
        s = ' '*4*indent + unicode(line)
        if tout:
            tout.write(s + '\n')
        r += [s]
    return r
def treset():
    global indent
    indent = 0

def safeget(cfg,a,b,c=None):
    try:
        return cfg.get(a,b)
    except:
        return c

DIR = appdirs.AppDirs('cardmode')

# ENSURE PROGRAM DIRS
for progdir in (DIR.user_config_dir,):
    try:
        os.makedirs(progdir)
    except OSError:
        pass

cfg = RawConfigParser()

# LOAD CONFIG
CONFIG_FN = os.path.join(DIR.user_config_dir, 'config.ini')
try:
    cfg.readfp(open(CONFIG_FN))
except:
    open(CONFIG_FN,'a+').close()
    os.chmod(CONFIG_FN, 0o600) # u=rw
    with open(CONFIG_FN, 'wb') as cfgfile:
        tmpcfg = ConfigParser()
        tmpcfg.add_section('defaults')
        tmpcfg.set('defaults','service','trello')
        tmpcfg.set('defaults','board','')
        tmpcfg.add_section('trello')
        tmpcfg.set('trello','apikey','')
        tmpcfg.set('trello','token','')
        tmpcfg.write(cfgfile)
    print('Trello credentials must be specified here:')
    print(CONFIG_FN)
    sys.exit(1)

# CREATE CACHE
CACHE_FN = os.path.join(DIR.user_config_dir, 'cache.ini')
cache = RawConfigParser()
if not os.path.exists(CACHE_FN):
    open(CACHE_FN,'a+').close()
    os.chmod(CACHE_FN, 0o600) # u=rw
cache.readfp(open(CACHE_FN))

try:
    SERVICE = args['--service'][0]
except:
    SERVICE = 'trello'

try:
    BOARD = args['--board'][0]
except:
    BOARD = args['ACTION'][0]
    if not BOARD:
        print(__doc__)
        sys.exit(1)

if SERVICE == 'trello':

    TRELLO_API_KEY = safeget(cfg,'trello','apikey')
    if not TRELLO_API_KEY:
        print('Trello credentials must be specified here:')
        print(CONFIG_FN)
        sys.exit(1)
    TRELLO_TOKEN = safeget(cfg,'trello','token')
    if not TRELLO_TOKEN:
        print('Trello credentials must be specified here:')
        print(CONFIG_FN)
        sys.exit(1)
    TRELLO_GET_BOARDS = 'https://trello.com/1/members/me/boards/'
    # TRELLO_GET_BOARD = 'https://trello.com/1/boards/'+boardid+'/cards'

    retry = False
    while True:
        # try:
        #     # board ids are 14-len hex
        #     if len(BOARD)!=14:
        #         raise ValueError()
        #     int('0x'+BOARD, 16)
        #     break
        # except ValueError:
            # board name -> id through cfg
        try:
            cache.add_section('trello_boards')
        except configparser.DuplicateSectionError:
            pass
        boardid = safeget(cache, 'trello_boards', BOARD)
        if boardid:
            BOARDNAME = BOARD
            BOARD = boardid
            break

        if retry:
            print('Board not found: ' + BOARD)
            sys.exit(1)

        # unknown ID, dump trello board names and ids
        params = {
            'key': TRELLO_API_KEY,
            'token': TRELLO_TOKEN,
            'fields': 'id,name'
        }
        res = requests.get(TRELLO_GET_BOARDS, params)
        if res.status_code != 200:
            print('Invalid board: ' + BOARD)
            sys.exit(1)
        j = res.json()
        print(j)
        for r in j:
            cache.set('trello_boards',r['name'],r['id'])
            print(r['name'])
            if r['name'].lower() == BOARD.lower():
                BOARD = r['id']
        with open(CACHE_FN, 'wb') as cachefile:
            cache.write(cachefile)
        retry = True

    params = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_TOKEN,
        'lists': 'open',
        'cards': 'open',
        'filter': 'all',
        'fields': 'all',
        'checklists': 'all',
        'checklist_fields': 'all',
        'checkItems': 'all',
        'checkItem_fields': 'all',
        'members': 'all',
        'member_fields': 'all',
        'board_lists': 'all',
        'board_fields': 'all',
    }

    tout = open(BOARDNAME+'.cardmode','w')
    toutjson = open(BOARDNAME+'.cardmode.json','w')

    TRELLO_GET_LISTS = 'https://trello.com/1/boards/'+BOARD
    res = requests.get(TRELLO_GET_LISTS, params)
    if res.status_code!=200:
        print('Error: ' + res.text)
        sys.exit(1)
    j = res.json()
    toutjson.write(json.dumps(j,indent=4))
    toutjson.close()

    jchecklists = j['checklists']
    checklists = {}
    for chk in jchecklists:
        checklists[chk['id']] = chk
    lists = OrderedDict()
    for l in j['lists']:
        lists[l['id']] = l
        print(lists)
    for c in j['cards']:
        col = lists[c['idList']]
        if not 'cards' in col:
            col['cards'] = []
        col['cards'].append(c)
else:
    pass

def json_to_cm(s):
    treset()

    i = 0
    r = tprint('[$board:' + BOARDNAME + ',$id:' + BOARD + ',$service:'+SERVICE+']')
    r += tprint()
    if SERVICE == 'trello':
        for colid,col in lists.items():
            if i>0: r += tprint()
            r += tprint(col['name'] + ': [$id:'+str(colid) + ']')
            tindent()
            # for card in cards:
            if 'cards' in col and col['cards']:
                for card in col['cards']:
                    r += tprint(card['name'] + ': ' + '[$id:' + card['id'] + ',$dateLastActivity:' + card['dateLastActivity'] + ']')
                    # r += tprint(card['name'] + ': ')
                    tindent()
                    # r += tprint('$id: ' + card['id'])
                    # r += tprint('$dateLastActivity: ' + card['dateLastActivity'])
                    # r += tprint('$url: ' + card['url'])
                    # r += tprint('$pos: ' + unicode(card['pos']))
                    if 'idChecklists' in card and card['idChecklists']:
                        for checklist in card['idChecklists']:
                            chk = checklists[checklist]
                            r += tprint(chk['name'] + ": checklist: [$id:" + chk['id'] + ']')
                            tindent()
                            # r += tprint('$id: ' + chk['id'])
                            for item in chk['checkItems']:
                                sym = '[x]' if item['state']=='complete' else '[ ]'
                                r += tprint(sym + ' ' + item['name'] + ' [$id:' + item['id'] + ']')
                                # r += tprint(sym + ' ' + item['name'])
                                # tindent()
                                # r += tprint('$id: ' + item['id'])
                                # toutdent()
                            toutdent()
                    if 'desc' in card and card['desc']:
                        r += tprint()
                        r += tprint(card['desc'])
                        r += tprint()
                    toutdent()
            toutdent()
            i += 1
    else:
        pass

    return r

def cm_to_json(s):
    j = {}
    
    return j

json_to_cm(col)

tout.close()
tout = None

