# datetime_schedule
#
# @desc     Executes the function 'function' at the given time(s). This will
#               create a new thread for each scheduling event.
#
# @param    labmda      function    Function to be executed.
#
# @param    int / [int] year            Year.
# @param    int / [int] month           Month.
# @param    int / [int] week            Week.
# @param    int / [int] day             Day.
# @param    int / [int] hour            Hour.
# @param    int / [int] minute          Minute.
# @param    int / [int] second          Second.
#
# @param    bool        catchup         Catch-up scheduling events that occured
#                                           when the script was not running.
# @param    int         catchup_delay   Max delay (in seconds) for starting the
#                                           catch-up jobs.
#
# @info     Set year / month / ... = None or empty list to execute the function
#               at every year / month / ...
def datetime_schedule(function, year, month, week, day, hour, minute, second, catchup = False, catchup_delay = None):
    # Convert time variables to lists, if necessary
    if not year is None or not year:
        if isinstance(year, list):
            years = year
        else:
            years = [year]

    if not month is None or not month:
        if isinstance(month, list):
            months = month
        else:
            months = [month]

    if not week is None or not week:
        if isinstance(week, list):
            weeks = week
        else:
            weeks = [week]

    if not day is None or not day:
        if isinstance(year, list):
            days = day
        else:
            days = [day]

    if not hour is None or not hour:
        if isinstance(hour, list):
            hours = hour
        else:
            hours = [hour]

    if not minute is None or not minute:
        if isinstance(minute, list):
            minutes = minute
        else:
            minutes = [minute]

    if not second is None or not second:
        if isinstance(year, list):
            seconds = second
        else:
            seconds = [second]

    # add event(s) to scheduler


# reccuring_schedule
#
# @desc     Executes the function 'function' every delay seconds.
#
# @param    labmda      function        Function to be executed.
# @param    int         delay           Delay.
# @param    bool        delay_as_pause  If true: will pause delay seconds
#                                           between each scheduling event.
#                                       If false: starting time of scheduling
#                                           events is delay seconds apart.
# @param    int         max_jobs        Maximum number of jobs running
#                                           simultaneously.
# @param    int         queue_length    Length of the queue containing missed
#                                           scheduling events.
def reccuring_schedule(function, delay, delay_as_pause, max_jobs = 1, queue_length = 0):
    # perform scheduling
    pass
