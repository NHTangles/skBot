from telegram.ext import Updater, InlineQueryHandler, CommandHandler, PicklePersistence
from telegram import ParseMode
import requests
#import re
import logging
from datetime import datetime, timezone, time, timedelta
from dateutil.tz import gettz
from warnings import filterwarnings, resetwarnings

#import bz2
#import json

from local import BOTTOKEN

# Let's do this with classes for something different.

# Scoreboard Period - day/week/month/year/alltime
# start/end timestamps of period,
# Name of period - 'July 2020', 'Wednesday, August 14, 2008', '2016'
# datetime objects marking the start and end of the period)
# sBMember objects for members active in that period
# addscore() method that deals with creating new members if necessary
#
class sbPeriod:
    def __init__(self, board, name, start, end):
        self.name = name
        self.board = board
        self.start = start
        self.end = end
        self.scores = {}

    def addScore(self, user, s):
        self.scores[user] = s + self.scores.get(user,0)

    def timeInPeriod(self, tm):
        return self.start < tm and self.end > tm

    def addScoreIfTime(self, user, s, tm):
        if self.timeInPeriod(tm):
            self.addScore(user, s)

    def formatScores(self, nicks):
        if self.timeInPeriod(datetime.now(self.board.tz)):
            current = ' (current)'
        else:
            current = ''
        message = '{0} for {1}{2}:'.format(self.board.units, self.name, current)

        for rank, usr in enumerate(sorted(self.scores, key=lambda x: self.scores[x], reverse = True), start=1):
            message += '\n{rank: >2}. {usr: <16} {score: >9}'.format(usr=getNickOrDefault(nicks,usr), rank=rank, score=str(self.scores[usr]))
        return message

# Actual Scoreboard object
# sBPeriod objects for current/previous d/w/m/y and alltime.
# add() methods for current/prev day, adds to all relevant sBPeriods
# logic for rolling days/weeks/months/years
class scoreBoard:
    # constructor - initial setup
    def __init__(self, name, tz, owner):
        self.name = name
        self.tz = tz
        self.owner = owner
        curtime = datetime.now(tz)
        start = curtime.replace (hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        self.today = sbPeriod(self, curtime.strftime("%A, %B %d, %Y"), start, end)
        weekstart = start - timedelta(days=start.weekday())
        end = weekstart + timedelta(days=7)
        self.thisweek = sbPeriod(self, curtime.strftime("Week %U, %Y"), weekstart, end)
        if start.month == 12:
            endmonth = 1
            endyear = start.year + 1
        else:
            endmonth = start.month + 1
            endyear = start.year
        monthstart = start.replace(day=1)
        end = start.replace(day=1, month=endmonth, year=endyear)
        self.thismonth = sbPeriod(self, curtime.strftime("%B, %Y"), monthstart, end)
        yearstart = start.replace(day=1,month=1)
        end = yearstart.replace(year=yearstart.year + 1)
        self.thisyear = sbPeriod(self, curtime.strftime("%Y"), yearstart, end)
        # "all time" starts when it's created.
        dtmax = datetime.max
        dtmax = dtmax.replace(tzinfo=tz)
        self.alltime = sbPeriod(self, "all time", curtime, dtmax)
        self.unit = "point"
        self.units = "points"
        self.yesterday = self.lastweek = self.lastmonth = self.lastyear = None

    def setTZ(self, tz):
        self.tz = tz

    def setUnit(self, unit, units = None):
        self.unit = unit
        if units:
            self.units = units
        else:
            self.units = unit
            if unit[-1] == 's' or unit[-1] == 'x':
                self.units += 'e'
            self.units += 's'

    # roll the periods, based on current time - must be called periodically using a timer.
    # ideally on the quarter-hour to accommodate even the weirdest timezones.
    def rollover(self):
        curtime = datetime.now(self.tz)
        if curtime < self.today.end:
            return # day has not changed - nothing to do
        self.yesterday = self.today
        start = curtime.replace (hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        self.today = sbPeriod(self, curtime.strftime("%A, %B %d, %Y"), start, end)
        if curtime >= self.thisweek.end:
            self.lastweek = self.thisweek
            weekstart = start - timedelta(days=start.weekday())
            end = weekstart + timedelta(days=7)
            self.thisweek = sbPeriod(self, curtime.strftime("Week %U, %Y"), weekstart, end)
        if curtime < self.thismonth.end:
            return # nothing to do for month/year
        self.lastmonth = self.thismonth
        monthstart = start.replace(day=1)
        end = start.replace(day=1, month=endmonth, year=endyear)
        self.thismonth = sbPeriod(self, curtime.strftime("%B, %Y"), monthstart, end)
        if curtime < self.thisyear.end:
            return
        self.lastyear = self.thisyear
        yearstart = start.replace(day=1,month=1)
        end = yearstart.replace(year=yearstart.year + 1)
        self.thisyear = sbPeriod(self, curtime.strftime("%Y"), yearstart, end)

    def addScore(self, user, nick, points, yday = False):
        addtime = datetime.now(self.tz)
        if yday:
            addtime -= timedelta(days=1)
        for period in [ self.today, self.yesterday,
                        self.thisweek, self.lastweek,
                        self.thismonth, self.lastmonth,
                        self.thisyear, self.lastyear,
                        self.alltime ]:
            if period: period.addScoreIfTime(user, points, addtime)
        return "{score} {u} added for {nick}".format(score=points, u=self.unit if points == 1 else self.units, nick=nick)

def init(context):
    log = logging.getLogger('skbot')
    log.info('init called - starting up.')
    if not context.bot_data.get('global_init', False):
        log.warning('init - initialising global state from scratch...')
        context.bot_data['global_init'] = True # so we know we've been here (or read persistent state from file)

def start(update, context):
    chat = update.effective_chat.id
    cd = context.chat_data
    if 'scores' not in cd:
        cd['scores'] = {}
    context.bot.send_message(chat_id=chat, text="To get started, please create a new scoreboard, with /newboard")
    context.bot.send_message(chat_id=chat, text='Type "/help" for more')

# Obligatory random.dog pic from sample code.
def get_url():
    contents = requests.get('https://random.dog/woof.json').json()
    url = contents['url']
    return url

def bop(update, context):
    url = get_url()
    chat_id = update.effective_chat.id
    context.bot.send_photo(chat_id=chat_id, photo=url)

def newBoard(update, context):
    cd = context.chat_data
    bd = context.bot_data
    chat = update.effective_chat.id
    user = update.effective_user
    log = logging.getLogger('skbot')
    if len(context.args) > 0:
        if 'scores' not in cd:
            cd['scores'] = {}
        nb = context.args[0]
        if nb in cd['scores']:
            context.bot.send_message(chat_id=chat, text="Scoreboard {0} already exists!".format(nb))
        else:
            cd['scores'][nb] = scoreBoard(nb,cd.get('tz',gettz('UTC')), user)
            if 'defSB' not in cd: cd['defSB'] = cd['scores'][nb]
            context.bot.send_message(chat_id=chat,
                                     text='New scoreboard {0} created.'.format(nb))
            if 'boards' not in bd: bd['boards'] = []
            bd['boards'].append(cd['scores'][nb])
    else:
        context.bot.send_message(chat_id=chat, text='Usage: /newboard <boardName>.')

def delBoard(update, context):
    cd = context.chat_data
    bd = context.bot_data
    chat = update.effective_chat.id
    user = update.effective_user
    if len(context.args) == 0:
        context.bot.send_message(chat_id=chat, text='Usage: /delboard <boardName>.')
        return
    board = getBoard(context, chat, context.args[0])
    if not board:
        context.bot.send_message(chat_id=chat, text='No such board: ' + context.args[0])
        return
    if board.owner.id !=  user.id:
        context.bot.send_message(chat_id=chat,
                text='Board {0} can only be deleted by {1}'.format(board.name,
                        getNickOrDefault(bd['nicks'],board.owner)))
        return
    bd['boards'].remove(board)
    del cd['scores'][context.args[0]]
    context.bot.send_message(chat_id=chat, text='board {0} deleted.'.format(context.args[0]))

def getBoard(context, chat, name):
    cd = context.chat_data
    if(name):
        try:
            return cd['scores'][name]
        except:
            context.bot.send_message(chat_id=chat,
                text='Scoreboard {0} does not exist.\nUse /newboard to create it'.format(name))
            return None
    try:
        return cd['defSB']
    except:
        context.bot.send_message(chat_id=chat,
              text='no scoreboards exist.\nUse /newboard to create one'.format(boardName))
        return None

def addScore(update, context):
    chat = update.effective_chat.id
    user = update.effective_user
    cd = context.chat_data
    nicks = context.bot_data.get('nicks',None)
    if len(context.args) > 1:
        boardName = context.args[1]
    else:
        boardName = None
    sb = getBoard(context, chat, boardName)
    if not sb: return
    try:
        score = int(context.args[0])
    except:
        context.bot.send_message(chat_id=chat,
             text='Usage: /add <points> [boardName] - points must be a whole number.')
        return
    context.bot.send_message(chat_id=chat,
         text=sb.addScore(user, getNickOrDefault(nicks, user), score))

def setUnits(update, context):
    chat = update.effective_chat.id
    cd = context.chat_data
    boardName = None
    if len(context.args) > 2:
        boardName = context.args[2]
    sb = getBoard(context, chat, boardName)
    if not sb: return

    if len(context.args) > 1:
        sb.setUnit(context.args[0], context.args[1])
    elif len(context.args) > 0:
        sb.setUnit(context.args[0])
    else:
        context.bot.send_message(chat_id=chat,
                text = "Usage: /unit <unit> [units [scoreboard]]\nunit (singular, required); units (plural); name of scoreboard to apply units" )

def setTZ(update, context):
    chat = update.effective_chat.id
    cd = context.chat_data
    try:
        tzname = context.args[0]
    except:
        context.bot.send_message(chat_id=chat, text = "Usage: /settz <tzname>" )
        return
    filterwarnings('error')
    try:
        tz = gettz(tzname)
    except:
        context.bot.send_message(chat_id=chat,
                text = "TZ {0} not recognised. Try something like /settz Australia/Canberra".format(tzname) )
        return
    resetwarnings()
    if 'scores' in cd:
        for sb in cd['scores']:
            sb.setTZ(tz)
    cd['tz'] = tz

def listcmds(update, context):
    msg = ''
    for (name, callback, desc) in commands:
        msg += '/{0}: {1}\n'.format(name, desc)
    context.bot.send_message(chat_id=update.effective_chat.id, text = msg)

def printScores(update, context):
    chat = update.effective_chat.id
    cd = context.chat_data
    nicks = context.bot_data.get('nicks', None)
    usage = "/scores [period [board]] period=day,week,month,year,yesterday,lastweek,lastmonth,lastyear,all"
    boardName = None
    if len(context.args) > 1:
        boardName = context.args[1]
    sb = getBoard(context, chat, boardName)
    if not sb: return
    lookup = { "day"  : sb.today,     "yesterday": sb.yesterday,
               "week" : sb.thisweek,  "lastweek" : sb.lastweek,
               "month": sb.thismonth, "lastmonth": sb.lastmonth,
               "year" : sb.thisyear,  "lastyear" : sb.lastyear,
               "all"  : sb.alltime }
    if len(context.args) > 0:
        period = context.args[0]
        if period not in lookup:
            context.bot.send_message(chat_id=chat, text = usage);
            return
    else:
        period = "day"
    if not lookup[period]:
        context.bot.send_message(chat_id=chat,
                text = "No scores for {0}.".format(period));
        return
    try:
         msg = lookup[period].formatScores(nicks)
    except:
        context.bot.send_message(chat_id=chat, text = usage);
        return
    context.bot.send_message(chat_id=chat, text = msg);

def listBoards(update, context):
    chat = update.effective_chat.id
    cd = context.chat_data
    sblist = []
    if 'scores' not in cd:
        context.bot.send_message(chat_id=chat, text = "No scoreboards!");
        return
    for sb in cd['scores'].keys():
        sblist.append('{0}{1}'.format(sb,' [default]' if cd['scores'][sb] == cd['defSB'] else ''))
    context.bot.send_message(chat_id=chat, text = "\n".join(sblist));

def updateNick(bd, userid, nick):
    if "nicks" not in bd:
        bd["nicks"] = {}
    if nick:
        bd["nicks"][userid] = nick
    else:
        if bd["nicks"][userid]: del bd["nicks"][userid]

def getNick(nicks, userid):
    if not nicks: return None
    return nicks.get(userid, None)

def getNickOrDefault(nicks, user):
    nick = getNick (nicks, user.id)
    if nick: return nick
    if user.username: return user.username
    else: return user.first_name


def setNick(update, context):
    chat = update.effective_chat.id
    userid = update.effective_user.id
    bd = context.bot_data
    if len(context.args) > 0:
        nick = context.args[0]
        updateNick(bd, userid, nick)
        context.bot.send_message(chat_id=chat, text = "Nick set to {0}.".format(nick));
    else:
        oldNick = getNick(bd.get('nicks',None), userid)
        if oldNick:
            updateNick(bd, userid, None)
            context.bot.send_message(chat_id=chat, text = "Nick for {0} removed.".format(oldNick));
        else:
            context.bot.send_message(chat_id=chat, text = "No nick set.");

def rolloverPeriods(context):
    if 'boards' not in context.bot_data: return
    for sb in context.bot_data['boards']:
        sb.rollover()

commands = [('start', start, 'Start a session with the bot - provides some basic instructions'),
            ('newboard', newBoard, 'create a new scoreboard'),
            ('delboard', delBoard, 'delete a scoreboard forever'),
            ('listboards', listBoards, 'List the scoreboards for this chat group'),
            ('unit', setUnits, 'set the unit of scoring for a scoreboard (eg push-ups)'),
            ('settz', setTZ, 'set the timeone for all scoreboards in the chat'),
            ('setnick', setNick, 'Set a nickname for the bot to call you'),
            ('add', addScore, 'Add to scoreboard for current user'),
            ('scores', printScores, 'Print current scores and rankings'),
            ('help', listcmds, 'Show this list of commands and what they do'),
            ('woof', bop, 'Print a doggy picture, for no reason') ]

def main():
    updater = Updater(token=BOTTOKEN,
                      persistence=PicklePersistence(filename='skbot.dat'),
                      use_context=True)
    dp = updater.dispatcher
    jq = updater.job_queue
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    jq.run_once(init, when=0)
    for (name, callback, desc) in commands:
        dp.add_handler(CommandHandler(name, callback))

    # Make this run every 15 minutes, on the quarter-hour
    jq.run_repeating(rolloverPeriods, interval=900, first=(900 - datetime.now().second % 900))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
