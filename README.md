This is a Telegram bot for tracking any kind of leaderboard between members of a chat group.

eg: Keep a tally of daily push-ups between you and your friends.

Basic instructions - create a telegram group for your friends, and add this bot to the group.

Run the following:

/newboard PushUps (creates a new scoreboard - you can have different scoreboards in the same group, such as another for SitUps if you're into that sort of thing - don't bother with PullUps though.  Tom will just destroy you even though he hasn't done any for months.  What a jerk)

Do some pushups.  Don't be lazy.  Make sure your form is good.  That is important for the next part:

/add 20 (or /add 20 PushUps if you have more than one scoreboard)

If you were so exhausted you forgot to enter your pushups, use /addy (add yesterday) instead, to enter them for the previous day.

Your friends will do the same when they see you have the most pushups, and you WILL have the most, until Dan comes along and does 1000 in a single day.  Classic Dan.

To display the scoreboard for various periods:
/day [scoreboard]   - shows scores so far for the current day
/week [scoreboard]  - shows scores for the current week
/month [scoreboard] - shows scores for the current month
/year [scoreboard]  - ... you get the idea
/total [scoreboard] - shows total scores since the scoreboard was created

Other stuff
/deleteboard PushUps - delete the scoreboard forever.  Only the user who created the scoreboard can delete it.

feature/pull requests welcome. 

If you want to run your own version of this, register a bot with BotFather, and place the bot token in local.py (see local.py.template)

then run the bot like this:

python3 skbot.py
