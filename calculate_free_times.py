import arrow
from dateutil import tz 
"""
most of these functions have an insane amout of arguments because I want to test these functions independantly from the flask app
"""

def normalize_ending_time(event, session_daily_end_time):
    #scales back end time if greater than daily end   
    #makes creating free time blocks easier.
    daily_end_time = session_daily_end_time.split(":")
    endTime = arrow.get(event['dateTime_end'])                     
    endTime = endTime.replace(hour=int(daily_end_time[0]), minute=int(daily_end_time[1]))   
    return endTime.isoformat()

def next_day(isotext):
    """
    ISO date + 1 day (used in query to Google calendar)
    """
    as_arrow = arrow.get(isotext)
    return as_arrow.replace(days=+1).isoformat()

def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars.  Each calendar is represented by a dict.
    The returned list is sorted to have
    the primary calendar first, and selected (that is, displayed in
    Google Calendars web app) calendars before unselected calendars.
    """
    print("Entering list_calendars")  
    calendar_list = service.calendarList().list().execute()["items"]
    result = [ ]
    for cal in calendar_list:
        kind = cal["kind"]
        id = cal["id"]
        if "description" in cal: 
            desc = cal["description"]
        else:
            desc = "(no description)"
        summary = cal["summary"]
        # Optional binary attributes with False as default
        selected = ("selected" in cal) and cal["selected"]
        primary = ("primary" in cal) and cal["primary"]
        
        result.append(
            {"kind": kind,
             "id": id,
             "summary": summary,
             "selected": selected,
             "primary": primary,
             })

    return sorted(result, key=cal_sort_key)

def cal_sort_key(cal):
    """
    Sort key for the list of calendars:  primary calendar first,
    then other selected calendars, then unselected calendars.
    (" " sorts before "X", and tuples are compared piecewise)
    """
    if cal["selected"]:
         selected_key = " "
    else:
         selected_key = "X"
    if cal["primary"]:
         primary_key = " "
    else:
         primary_key = "X"
    return (primary_key, selected_key, cal["summary"])

def list_events(service, calendarIDs, session_begin_date, session_end_date, session_daily_begin_time, session_daily_end_time, session_ignoreable_events): 
    print(session_end_date)
    print("Entering cft.list_events")
    then = next_day(session_end_date)
    results = []
    for calID in calendarIDs:
        eventsResult = service.events().list(
            calendarId=calID, timeMin=session_begin_date, timeMax=then, singleEvents=True,
            orderBy='startTime').execute()
        events = eventsResult.get('items', [])

        for event in events:

            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            event_id = event['id']

            dateTime_start = arrow.get(start)
            dateTime_end = arrow.get(end) 
            summary = event['summary']
            all_day_event = False

            if 'transparency' in event:
                print("Event '{}' skipped because it is transparent".format(summary))
                continue

            if session_ignoreable_events != None and event_id in session_ignoreable_events:
                print("Event '{}' ignored because it was selected as ignorable".format(summary))
                continue

            if str(dateTime_end.time()) == '00:00:00' and str(dateTime_start.time()) == '00:00:00':
                print("Event '{}' must be nontransparent all day event, will not skip".format(summary))
                dateTime_start = dateTime_start.replace(tzinfo='local')
                dateTime_end = dateTime_end.replace(minutes=-1, tzinfo='local')
                all_day_event = True

            elif str(dateTime_start.time()) <= session_daily_begin_time and str(dateTime_end.time()) >= session_daily_end_time:
                print("Event '{}' must be nontransparent really long, almost all day event, will not skip".format(summary))
                all_day_event = True

            elif str(dateTime_end.time()) <= session_daily_begin_time or str(dateTime_start.time()) >= session_daily_end_time:
                print("Event '{}' at {}-{} skipped, out of time range of {}-{}".format(
                                                                            summary, dateTime_start.time(), dateTime_end.time(), 
                                                                            session_daily_begin_time, session_daily_end_time))
                continue
                
            results.append(
                {"dateTime_start": dateTime_start.isoformat(),
                 "dateTime_end": dateTime_end.isoformat(),
                 "summary": summary,
                 "event_id": event_id,
                 "all_day_event": all_day_event,
                 })

    return sorted(results, key=event_sort_key)

def event_sort_key(event):
    return event['dateTime_start']

def get_busy_blocks(event_list, session_daily_end_time): 
    print('Entering cft.get_busy_blocks')
    events = []
    for i in range(len(event_list)):    #creates list of non overlapping events
        starti0 = arrow.get(event_list[i-1]['dateTime_start'])
        endi0 = arrow.get(event_list[i-1]['dateTime_end'])
        starti1 = arrow.get(event_list[i]['dateTime_start'])    
        endi1 = arrow.get(event_list[i]['dateTime_end'])
        if starti0 <= starti1 and endi0 >= endi1:
            print("Skipping event '{}' because it overlaps '{}' completely".format(event_list[i]['summary'], event_list[i-1]['summary']))
            continue
        events.append(event_list[i])

    # print("printing events that don't overlap completely with others")
    # for event in events:
    #     print(event)
    # print()
    if len(events) < 2:
        print('len(events) < 2, returning events')
        return events

    busy_blocks = []
    for i in range(len(events)-1):      #combines events into busy blocks
        endi0 = arrow.get(events[i]['dateTime_end'])
        starti1 = arrow.get(events[i+1]['dateTime_start'])
        if endi0 >= starti1:
            events[i+1]['dateTime_start'] = events[i]['dateTime_start']
            # print("comparing '{0}' to '{1}', extending '{1}' to {2}-{3}\n".format(events[i]['summary'], events[i+1]['summary'], arrow.get(events[i+1]['dateTime_start']).time(), arrow.get(events[i+1]['dateTime_end']).time()))
        else:
            if str(endi0.time()) > session_daily_end_time:
                events[i]['dateTime_end'] = normalize_ending_time(events[i], session_daily_end_time)                  
            # print("appending '{}'".format(events[i]['summary']))
            busy_blocks.append(events[i])

    if str(arrow.get(events[-1]['dateTime_end']).time()) > session_daily_end_time:
        events[-1]['dateTime_end'] = normalize_ending_time(events[-1], session_daily_end_time)   
    # print("appending '{}'".format(events[-1]['summary']))       
    busy_blocks.append(events[-1])

    # print("appended busy blocks")
    # for event in busy_blocks:
    #     print(event)
    # print()

    return busy_blocks

def calc_free_times(busy_blocks, session_begin_date, session_end_date, session_daily_begin_time, session_daily_end_time):
    print('Entering cft.calc_free_times')
    begin_date = arrow.get(session_begin_date)
    end_date = arrow.get(session_end_date)
    days = (end_date-begin_date).days

    daily_begin_time = session_daily_begin_time.split(":")
    daily_end_time = session_daily_end_time.split(":")

    day_dateTime_begin = begin_date.replace(hour=int(daily_begin_time[0]), minute=int(daily_begin_time[1]))
    day_dateTime_end = begin_date.replace(hour=int(daily_end_time[0]), minute=int(daily_end_time[1]))

    free_times = []
    for i in range(days+1):     #creates list of free times that span from daily_begin_time to daily_end_time each day in the date range 
        free_times.append(
            {"dateTime_start": day_dateTime_begin.isoformat(),
             "dateTime_end": day_dateTime_end.isoformat(),
             "summary": 'free time',
             })
        day_dateTime_begin = day_dateTime_begin.replace(days=+1)
        day_dateTime_end = day_dateTime_end.replace(days=+1)


    for i, busy_time in enumerate(busy_blocks):     #calculates actual times in free_times that are not blocked by busy_times
        current_time = busy_time['dateTime_start']
        for j, free_time in enumerate(free_times):
            if busy_time['all_day_event'] and busy_time['dateTime_start'] <= free_time['dateTime_start']:
                del free_times[j]
                break
            elif busy_time['dateTime_end'] <= free_time['dateTime_start']:
                # print('continuing {} <= {}'.format(busy_time['dateTime_end'], free_time['dateTime_start']))
                continue

            if busy_time['dateTime_end'] <= free_time['dateTime_end']:
                part1 = {"dateTime_start": free_time['dateTime_start'],
                         "dateTime_end": busy_time['dateTime_start'],
                         "summary": 'free time',
                        }
                part2 = {"dateTime_start": busy_time['dateTime_end'],
                         "dateTime_end": free_time['dateTime_end'],
                         "summary": 'free time',
                        }
                # print('deleting \n{} and appending \n{} and \n{}\n'.format(free_times[j], part1, part2))
                del free_times[j]

                if part1['dateTime_start'] < part1['dateTime_end']: #makes sure parts have positive time span
                    free_times.append(part1)

                if part2['dateTime_start'] < part2['dateTime_end']: #negative or 0 time span would not make sense
                    free_times.append(part2)
                break

        free_times.sort(key=event_sort_key)

    return free_times