# MeetMe
### Doodle like meeting scheduler that imports users' Google calendars 

## What is here

Application allows multiple users to import calendars though the Google calendar API.  
Users are allowed to choose 'blocking' appointments between a start and end date. 
After everyone has imported their calendars the application will list shared free times 
based on the date range given and the events taken from the calendars.


## What you'll need to add to configure project

You'll need a 'client secret' file of your own. This is kind of a
developer key, which you need to obtain from Google.  See
https://auth0.com/docs/connections/social/google and
https://developers.google.com/identity/protocols/OAuth2 .
The applicable scenario for this project is 'Web server applications'.  


### What do I need?  Where will it work? ###

* Designed for Unix, mostly interoperable on Linux (Ubuntu) or MacOS.
  Target environment is Raspberry Pi. 
  
  ** May also work on Windows (at least the W10 Ubuntu bash) or a Linux virtual machine out of the box depending on your pyvenv package command name. 
  
* Program expects `make configure` to be run first but might require manual configuration by changing the PYVENV command name in templates.d/Makefile.standard between pyvenv and virtualenv. I could not get "pyvenv" to install on my pi or anywhere else but virtualenv worked everywhere.  

If you can run flask applications in your development environment, the
application would might be run by
  `python3 flask_main.py` or `make run`
and then reached with url
  `http://localhost:5000`

## Author 
Michal Young

Edited by
Clayton Kilmer, kilmer@cs.uoregon.edu


