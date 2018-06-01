#!/usr/bin/python2
from __future__ import unicode_literals, print_function
import os, sys, six, requests, json
import six.moves.configparser as configparser
from six.moves.configparser import ConfigParser,RawConfigParser
import appdirs
from collections import OrderedDict

indent = 0
tout=None
def tindent(i=1):
    global indent
    indent += i
def toutdent(i=1):
    global indent
    indent -= i
def tprint(lines=''):
    lines = ''.join(lines).split('\n')
    for line in lines:
        # TODO: escape this stuff
        print(' '*4*indent + unicode(line))
        if tout:
            tout.write(' '*4*indent + unicode(line) + '\n')
def treset():
    global indent
    indent = 0

def safeget(cfg,a,b,c=None):
    try:
        return cfg.get(a,b)
    except:
        return c

DIR = appdirs.AppDirs('flipcoder','cardmode')

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
    with open(CONFIG_FN, 'wb') as cfgfile:
        tmpcfg = ConfigParser()
        tmpcfg.add_section('trello')
        tmpcfg.set('trello','apikey','')
        tmpcfg.set('trello','token','')
        tmpcfg.set('trello','default_board','')
        tmpcfg.write(cfgfile)
    print('Trello credentials must be specified here:')
    print(CONFIG_FN)
    sys.exit(1)

# CREATE CACHE
CACHE_FN = os.path.join(DIR.user_config_dir, 'cache.ini')
cache = RawConfigParser()
if not os.path.exists(CACHE_FN):
    open(CACHE_FN,'a+').close()
cache.readfp(open(CACHE_FN))

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

try:
    BOARD = sys.argv[1]
except IndexError:
    try:
        BOARD = cfg.get('trello','default_board')
    except:
        print('No default board.  Specify board name or set default_board.')
        sys.exit(1)

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
        if r['name'] == BOARD:
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

tout = open(BOARDNAME+'.trello','w')
toutjson = open(BOARDNAME+'.trello.json','w')

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

i = 0
tprint('$board: ' + BOARDNAME)
tprint('$id: ' + BOARD)
tprint()
for colid,col in lists.items():
    if i>0: tprint()
    tprint(col['name'] + ': ')
    tindent()
    tprint('$id: ' + colid)
    # for card in cards:
    for card in col['cards']:
        tprint(card['name'] + ': ')
        tindent()
        tprint('$id: ' + card['id'])
        tprint('$dateLastActivity: ' + card['dateLastActivity'])
        tprint('$url: ' + card['url'])
        # tprint('$pos: ' + unicode(card['pos']))
        for checklist in card['idChecklists']:
            chk = checklists[checklist]
            tprint(chk['name'] + ":" + "Checklist")
            tindent()
            tprint('$id: ' + chk['id'])
            for item in chk['checkItems']:
                sym = '[x]' if item['state']=='complete' else '[ ]'
                tprint(sym + ' ' + item['name'])
                tindent()
                tprint('$id: ' + item['id'])
                toutdent()
            toutdent()
        if card['desc']:
            tprint()
            tprint(card['desc'])
            tprint()
        toutdent()
    toutdent()
    i += 1

tout.close()
tout = None

