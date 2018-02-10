# MeetMe
Snarf appointment data from a selection of a user's Google calendars 

## What is here

The application allows the user to choose calendars (a single
user may have several Google calendars, one of which is the 'primary'
calendar) and list 'blocking'  (non-transparent)
appointments between a start date and an end date
for some subset of them. Can also then list free times based on the date range given and the events taken from the calendars. 

## What you'll need to add to configure project

You'll need a 'client secret' file of your own. This is kind of a
developer key, which you need to obtain from Google.  See
https://auth0.com/docs/connections/social/google and
https://developers.google.com/identity/protocols/OAuth2 .
The applicable scenario for this project is 'Web server applications'.  


### What do I need?  Where will it work? ###

* Designed for Unix, mostly interoperable on Linux (Ubuntu) or MacOS.
  Target environment is Raspberry Pi. 
  ** May also work on Windows (at least the W10 Ubuntu bash) or a Linux virtual machine
   out of the box depending on your pyvenv package command name. Program expects `make configure` to be run first but might require manual configuration by changing the PYVENV command name in templates.d/Makefile.standard between pyvenv and virtualenv. I could not get "pyvenv" to install on my pi or anywhere else but virtualenv worked everywhere.  

If you can run flask applications in your development environment, the
application would might be run by
  `python3 flask_main.py` or `make run`
and then reached with url
  `http://localhost:5000`

## Author 
Michal Young

Edited by
Clayton Kilmer, kilmer@cs.uoregon.edu


