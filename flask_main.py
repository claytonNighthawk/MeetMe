import flask
from flask import render_template
from flask import request
from flask import url_for
import uuid

import json
import logging

# Date handling 
import arrow # Replacement for datetime, based on moment.js
# import datetime # But we still need time
from dateutil import tz  # For interpreting local times


# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services 
from apiclient import discovery

###
# Globals
###
import calculate_free_times as cft
import CONFIG
import secrets.admin_secrets  # Per-machine secrets
import secrets.client_secrets # Per-application secrets
from uuid import uuid4

import pymongo
from pymongo import MongoClient
MONGO_CLIENT_URL = "mongodb://{}:{}@localhost:{}/{}".format(
    secrets.client_secrets.db_user,
    secrets.client_secrets.db_user_pw,
    secrets.admin_secrets.port, 
    secrets.client_secrets.db)

app = flask.Flask(__name__)
app.debug=CONFIG.DEBUG
app.logger.setLevel(logging.DEBUG)
app.secret_key=CONFIG.secret_key

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = secrets.admin_secrets.google_key_file  ## You'll need this
APPLICATION_NAME = 'MeetMe class project'

BAD_URL_CHARS = {" ": '%20', } #should be filled in more

####
# Database connection per server process
###

try: 
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, secrets.client_secrets.db)
    collection = db.dated

except:
    print("Failure opening database. Is Mongo running? Correct password?")
    sys.exit(1)

####
#
#  Pages (routed from URLs)
#
####

@app.route("/")
@app.route("/index")
def index():
    app.logger.debug("Entering index")
    init_session_values()
    return render_template('index.html')

@app.route('/contribute/<id>')
def contribute(id):
    init_contribute_values(id)
    busy_blocks = list(collection.find({"type": "busy_block", "session_id": flask.session['session_id']})) 
    flask.g.free_times = cft.calc_free_times(busy_blocks, flask.session['session_id'], flask.session['begin_date'], flask.session['end_date'], flask.session['daily_begin_time'], flask.session['daily_end_time'])
    return render_template('contribute.html')

@app.route("/choose", methods=['GET', 'POST'])
def choose():
    ## We'll need authorization to list calendars 
    ## I wanted to put what follows into a function, but had
    ## to pull it back here because the redirect has to be a
    ## 'return' 
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
        app.logger.debug("Redirecting to authorization")
        return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.g.calendars = cft.list_calendars(gcal_service)

    if 'calendar_ids' in flask.session:
        flask.g.events = cft.list_events(gcal_service, flask.session['calendar_ids'], flask.session['session_id'], flask.session['begin_date'], flask.session['end_date'], flask.session['daily_begin_time'], flask.session['daily_end_time'], flask.session['ignoreable_events'])   

        if len(flask.g.events) != 0:
            flask.session['email'] = flask.g.events[0]['email']
            collection.insert_many(flask.g.events)

    return render_template('index.html')

@app.route('/get_free_times', methods=['POST'])
def get_free_times():
    app.logger.debug('Redirecting to show free times page')
    events = list(collection.find({"type": "event", "session_id": flask.session['session_id']}).sort("dateTime_start"))

    busy_blocks = cft.get_busy_blocks(events, flask.session["daily_end_time"])
    for block in busy_blocks: 
        collection.replace_one({'_id': block['_id']}, block)
    busy_blocks = list(collection.find({"type": "busy_block", "session_id": flask.session['session_id']}).sort("dateTime_start"))          

    flask.g.free_times = cft.calc_free_times(busy_blocks, flask.session['session_id'], flask.session['begin_date'], flask.session['end_date'], flask.session['daily_begin_time'], flask.session['daily_end_time'])

    if not flask.session['contributing']:
        settings = {"type": "settings",
                    "session_id": flask.session['session_id'],
                    "emails": [flask.session['email']], #one element list to be added to by others
                    "begin_date": flask.session['begin_date'], 
                    "end_date": flask.session['end_date'],
                    "daterange": flask.session["daterange"], 
                    "daily_begin_time": flask.session['daily_begin_time'], 
                    "daily_end_time": flask.session['daily_end_time']
                   }
        if len(list(collection.find({"type": 'settings', "session_id": flask.session['session_id']}))) == 0:
            collection.insert_one(settings)
    else: 
        collection.update_one({"type": 'settings', "session_id": flask.session['session_id']}, 
                                                    {'$addToSet': {'emails': flask.session['email']}}) 
                                                    #add the current user email to setttings['emails']

    emails = list(collection.find({"type": 'settings', "session_id": flask.session['session_id'], }))[0]['emails']
    flask.g.emails = ", ".join(emails) # to get rid of the square brackets
    flask.g.message = 'Use this link to contribute to the meeting picker'
    flask.g.partialLinkback = '/contribute/' + flask.session['session_id']

    return render_template('free_times.html')

####
#
#  Google calendar authorization:
#      Returns us to the main /choose screen after inserting
#      the calendar_service object in the session state.  May
#      redirect to OAuth server first, and may take multiple
#      trips through the oauth2 callback function.
#
#  Protocol for use ON EACH REQUEST: 
#     First, check for valid credentials
#     If we don't have valid credentials
#         Get credentials (jump to the oauth2 protocol)
#         (redirects back to /choose, this time with credentials)
#     If we do have valid credentials
#         Get the service object
#
#  The final result of successful authorization is a 'service'
#  object.  We use a 'service' object to actually retrieve data
#  from the Google services. Service objects are NOT serializable ---
#  we can't stash one in a cookie.  Instead, on each request we
#  get a fresh serivce object from our credentials, which are
#  serializable. 
#
#  Note that after authorization we always redirect to /choose;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead. 
#
####


def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value. 
    """
    if 'credentials' not in flask.session:
        return None

    credentials = client.OAuth2Credentials.from_json(flask.session['credentials'])

    if (credentials.invalid or credentials.access_token_expired):
        return None
    return credentials

def get_gcal_service(credentials):
    """
    We need a Google calendar 'service' object to obtain
    list of calendars, busy times, etc.  This requires
    authorization. If authorization is already in effect,
    we'll just return with the authorization. Otherwise,
    control flow will be interrupted by authorization, and we'll
    end up redirected back to /choose *without a service object*.
    Then the second call will succeed without additional authorization.
    """
    app.logger.debug("Entering get_gcal_service")
    http_auth = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http_auth)
    app.logger.debug("Returning service")
    return service

@app.route('/oauth2callback')
def oauth2callback():
    """
    The 'flow' has this one place to call back to.  We'll enter here
    more than once as steps in the flow are completed, and need to keep
    track of how far we've gotten. The first time we'll do the first
    step, the second time we'll skip the first step and do the second,
    and so on.
    """
    app.logger.debug("Entering oauth2callback")
    flow =  client.flow_from_clientsecrets(
            CLIENT_SECRET_FILE,
            scope= SCOPES,
            redirect_uri=flask.url_for('oauth2callback', _external=True))
    ## Note we are *not* redirecting above.  We are noting *where*
    ## we will redirect to, which is this function. 
    
    ## The *second* time we enter here, it's a callback 
    ## with 'code' set in the URL parameter.  If we don't
    ## see that, it must be the first time through, so we
    ## need to do step 1. 
    app.logger.debug("Got flow")
    if 'code' not in flask.request.args:
        app.logger.debug("Code not in flask.request.args")
        auth_uri = flow.step1_get_authorize_url()
        return flask.redirect(auth_uri)
        ## This will redirect back here, but the second time through
        ## we'll have the 'code' parameter set
    else:
        ## It's the second time through ... we can tell because
        ## we got the 'code' argument in the URL.
        app.logger.debug("Code was in flask.request.args")
        auth_code = flask.request.args.get('code')
        credentials = flow.step2_exchange(auth_code)
        flask.session['credentials'] = credentials.to_json()
        ## Now I can build the service and execute the query,
        ## but for the moment I'll just log it and go back to
        ## the main screen
        app.logger.debug("Got credentials")
        return flask.redirect(flask.url_for('choose'))

#####
#
#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use. 
#
#####

@app.route('/choose_calendars', methods=['POST'])
def choose_calendars():
    cal_ids = request.form.getlist("to_read")
    flask.session['calendar_ids'] = cal_ids
    return flask.redirect(flask.url_for('choose'))

@app.route('/setrange', methods=['POST'])
def setrange():
    """
    User chose a date range with the bootstrap daterange
    widget.
    """
    app.logger.debug("Entering setrange")  
    daterange = request.form.get('daterange')
    flask.session['daterange'] = daterange
    timerange = [request.form.get('daily_begin_time'), request.form.get('daily_end_time')]

    flask.session['daterange'] = daterange
    daterange_parts = daterange.split()

    flask.session['begin_date'] = interpret_date(daterange_parts[0])
    flask.session['end_date'] = interpret_date(daterange_parts[2])
    flask.session['daily_begin_time'] = interpret_time(timerange[0])
    flask.session['daily_end_time'] = interpret_time(timerange[1])

    app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
        daterange_parts[0], daterange_parts[1], 
        flask.session['begin_date'], flask.session['end_date']))
    return flask.redirect(flask.url_for("choose"))

@app.route('/ignore_unimportant_events', methods=['POST'])
def ignore_unimportant_events():
    app.logger.debug('Entering ignore unimportant events')
    ignoreable_events = request.form.getlist('events_to_ignore')
    flask.session['ignoreable_events'] = ignoreable_events
    return flask.redirect(flask.url_for('choose'))

####
#
#   Initialize session variables 
#
####

def init_session_values():
    """
    Start with some reasonable defaults for date and time ranges.
    Note this must be run in app context ... can't call from main. 
    """
    app.logger.debug("initing session values")
    # Default date span = tomorrow to 1 week from now
    now = arrow.now('local')     # We really should be using tz from browser
    tomorrow = now.replace(days=+1)
    nextweek = now.replace(days=+7)

    flask.session["begin_date"] = tomorrow.floor('day').isoformat()
    flask.session["end_date"] = nextweek.ceil('day').isoformat()
    flask.session["daterange"] = "{} - {}".format(tomorrow.format("MM/DD/YYYY"), nextweek.format("MM/DD/YYYY"))
    # Default time span each day, 9 to 5

    flask.session["daily_begin_time"] = interpret_time("9am")
    flask.session["daily_end_time"] = interpret_time("5pm")
    if 'calendar_ids' in flask.session:
        flask.session.pop('calendar_ids')

    flask.session['ignoreable_events'] = None
    flask.session['session_id'] = str(uuid4().hex)[:16] # do not need all 32 characters at the moment
    flask.session['contributing'] = False

def init_contribute_values(id):
    """
    Start with some reasonable defaults for date and time ranges.
    Note this must be run in app context ... can't call from main. 
    """
    app.logger.debug("initing contribute values")
    settings = list(collection.find({"type": "settings", "session_id": id}))[0]
    app.logger.debug(settings)

    flask.session["begin_date"] = settings['begin_date']
    flask.session["end_date"] = settings['end_date']
    flask.session["daterange"] = settings['daterange']

    flask.session["daily_begin_time"] = settings['daily_begin_time']
    flask.session["daily_end_time"] = settings['daily_end_time']
    if 'calendar_ids' in flask.session:
        flask.session.pop('calendar_ids')

    flask.session['ignoreable_events'] = None
    flask.session['session_id'] = id
    flask.session['contributing'] = True

def interpret_time(text):
    """
    Read time in a human-compatible format and
    interpret as ISO format with local timezone.
    May throw exception if time can't be interpreted. In that
    case it will also flash a message explaining accepted formats.
    """
    # app.logger.debug("Decoding time '{}'".format(text))
    time_formats = ["ha", "h:mma",  "h:mm a", "H:mm"]
    try: 
        as_arrow = arrow.get(text, time_formats).replace(tzinfo='local')
        as_arrow = as_arrow.replace(year=2016) #HACK see below
        # app.logger.debug("Succeeded interpreting time")
    except:
        app.logger.debug("Failed to interpret time")
        flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm".format(text))
        raise
    return str(as_arrow.time())
    #HACK #Workaround
    # isoformat() on raspberry Pi does not work for some dates
    # far from now.  It will fail with an overflow from time stamp out
    # of range while checking for daylight savings time.  Workaround is
    # to force the date-time combination into the year 2016, which seems to
    # get the timestamp into a reasonable range. This workaround should be
    # removed when Arrow or Dateutil.tz is fixed.
    # FIXME: Remove the workaround when arrow is fixed (but only after testing
    # on raspberry Pi --- failure is likely due to 32-bit integers on that platform)

def interpret_date(text):
    """
    Convert text of date to ISO format used internally,
    with the local time zone.
    """
    try:
        as_arrow = arrow.get(text, "MM/DD/YYYY").replace(tzinfo='local')
    except:
            flask.flash("Date '{}' didn't fit expected format 12/31/2001")
            raise
    return as_arrow.isoformat()

####
#
#  Functions (NOT pages) that return some information are in calculate_free_times.py
#
####

####
#
# Functions used within the templates
#
####

@app.template_filter('fmtdate')
def format_arrow_date(date):
    try: 
        normal = arrow.get(str(date))
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"

@app.template_filter('fmttime')
def format_arrow_time(time):
    try:
        normal = arrow.get(str(time), 'HH:mm:ss')
        return normal.format("hh:mma")
    except Exception as e:
        app.logger.debug(e)
        return "(bad time)"

@app.template_filter('url_escapify')
def url_escapify(text):
    text = list(text)
    for i in range(len(text)):
        if text[i] in BAD_URL_CHARS:
            text[i] = BAD_URL_CHARS[text[i]]
    return ''.join(text)
        
#############


if __name__ == "__main__":
    # App is created above so that it will
    # exist whether this is 'main' or not
    # (e.g., if we are running under green unicorn)
    app.run(port=CONFIG.PORT,host="0.0.0.0")
        
