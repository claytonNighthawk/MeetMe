from calculate_free_times import *
import arrow

def same(real, expected):
    print(real, expected)
    return real == expected

session_begin_date = '2016-11-20T00:00:00-08:00' 
session_end_date = '2016-11-26T00:00:00-08:00'
session_daily_begin_time = '09:00:00' 
session_daily_end_time = '17:00:00'

'''
events test multiple different things at once
event 0 is a generic event
event 1 and event 2 test to see if get_busy_blocks with combine them
event 3 is an event that starts before the daily time window but overlaps that time we care about too so it needs to be included 
event 4 totally overlaps event 3 and so can be ignored
event 5 is an event that starts before the daily end time but goes past the end of the daily time window, this should be included 
event 6 is an all day event that tests if the program can handle events that begin before the time range and end after the time range 
'''
events = [{'dateTime_start': '2016-11-21T09:00:00-08:00', 'all_day_event': False, 'dateTime_end': '2016-11-21T11:00:00-08:00', 'summary': 'busy'},
          {'dateTime_start': '2016-11-21T12:00:00-08:00', 'all_day_event': False, 'dateTime_end': '2016-11-21T13:00:00-08:00', 'summary': "Events that touch but don't overlap 1"},
          {'dateTime_start': '2016-11-21T13:00:00-08:00', 'all_day_event': False, 'dateTime_end': '2016-11-21T14:00:00-08:00', 'summary': "Events that touch but don't overlap 2"},
          {'dateTime_start': '2016-11-23T07:00:00-08:00', 'all_day_event': False, 'dateTime_end': '2016-11-23T11:00:00-08:00', 'summary': 'Include this, partially overlaps span'},
          {'dateTime_start': '2016-11-23T08:30:00-08:00', 'all_day_event': False, 'dateTime_end': '2016-11-23T09:30:00-08:00', 'summary': 'Include this, overlapping event'},
          {'dateTime_start': '2016-11-23T16:00:00-08:00', 'all_day_event': False, 'dateTime_end': '2016-11-23T19:00:00-08:00', 'summary': 'Include this, partially overlaps span'},
          {'dateTime_start': '2016-11-24T00:00:00-08:00', 'all_day_event': True, 'dateTime_end': '2016-11-24T23:59:00-08:00', 'summary': 'All day event'}]

def test_get_busy_blocks():
    busy_blocks = [{'dateTime_end': '2016-11-21T11:00:00-08:00', 'dateTime_start': '2016-11-21T09:00:00-08:00', 'all_day_event': False, 'summary': 'busy'},
                   {'dateTime_end': '2016-11-21T14:00:00-08:00', 'dateTime_start': '2016-11-21T12:00:00-08:00', 'all_day_event': False, 'summary': "Events that touch but don't overlap 2"},
                   {'dateTime_end': '2016-11-23T11:00:00-08:00', 'dateTime_start': '2016-11-23T07:00:00-08:00', 'all_day_event': False, 'summary': 'Include this, partially overlaps span'},
                   {'dateTime_end': '2016-11-23T17:00:00-08:00', 'dateTime_start': '2016-11-23T16:00:00-08:00', 'all_day_event': False, 'summary': 'Include this, partially overlaps span'},
                   {'dateTime_end': '2016-11-24T17:00:00-08:00', 'dateTime_start': '2016-11-24T00:00:00-08:00', 'all_day_event': True, 'summary': 'All day event'}]
    assert same(get_busy_blocks(events, session_daily_end_time), busy_blocks)

def test_calc_free_times():
    busy_blocks = get_busy_blocks(events, session_daily_end_time)
    free_times = [{'dateTime_start': '2016-11-20T09:00:00-08:00', 'dateTime_end': '2016-11-20T17:00:00-08:00', 'summary': 'free time'},
                  {'dateTime_start': '2016-11-21T11:00:00-08:00', 'dateTime_end': '2016-11-21T12:00:00-08:00', 'summary': 'free time'},
                  {'dateTime_start': '2016-11-21T14:00:00-08:00', 'dateTime_end': '2016-11-21T17:00:00-08:00', 'summary': 'free time'},
                  {'dateTime_start': '2016-11-22T09:00:00-08:00', 'dateTime_end': '2016-11-22T17:00:00-08:00', 'summary': 'free time'},
                  {'dateTime_start': '2016-11-23T11:00:00-08:00', 'dateTime_end': '2016-11-23T16:00:00-08:00', 'summary': 'free time'},
                  {'dateTime_start': '2016-11-25T09:00:00-08:00', 'dateTime_end': '2016-11-25T17:00:00-08:00', 'summary': 'free time'},
                  {'dateTime_start': '2016-11-26T09:00:00-08:00', 'dateTime_end': '2016-11-26T17:00:00-08:00', 'summary': 'free time'}]
    assert same(calc_free_times(busy_blocks, session_begin_date, session_end_date, session_daily_begin_time, session_daily_end_time), free_times)
