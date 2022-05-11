from calendar import monthrange
import threading
import json
from datetime import datetime, timedelta
import time


# DEBUG: Test function. Can be removed after testing.
def test_function():
    print('Test function called.')


# This holds information about all tasks
schedule_tasks = { 'datetime': {}, 'reccuring': [] }


datetime_scheduler_cond = threading.Condition()
datetime_scheduler_thread = None

# New task ids will be added here. The datetime scheduler will then activate
#     these tasks according to the information in schedule_tasks.
datetime_tasks_added = []
datetime_tasks_added_lock = threading.Lock()


# datetime_scheduler_main
#
# @desc     This function will start the datetime tasks.
#
# @param    Condition() cond_obj    A threading condition object to manage
#                                       wait() and notify().
#
# @note     Since this function uses wait() and relies on being notify()ed, it
#               has to be executed in a seperate thread. Use notify() whenever a
#               new task is added.
def datetime_scheduler_main(cond_obj):
    global datetime_tasks_added
    global datetime_tasks_added_lock
    global schedule_tasks

    # <task_id> : <next_execution_time>
    tasks = {}

    # Wait for a task to be added
    with cond_obj:
        cond_obj.wait()

    while True:
        # check if new tasks were added
        datetime_tasks_added_lock.acquire()
        if datetime_tasks_added:
            for task in datetime_tasks_added:
                task_time = schedule_tasks['datetime'][task]['time']
                years   = task_time['years']
                months  = task_time['months']
                days    = task_time['days']
                hours   = task_time['hours']
                minutes = task_time['minutes']
                seconds = task_time['seconds']
                next_execution_time = get_next_execution_datetime(years, months, [], days, hours, minutes, seconds)

                tasks[task] = next_execution_time
            datetime_tasks_added = []
        datetime_tasks_added_lock.release()

        # get next task and execution time (seconds remaining) and start tasks
        max_wait = -1
        for task_id, task in tasks.items():
            time_diff = task - datetime.now()
            seconds_remaining = time_diff.total_seconds()

            if seconds_remaining > 0:
                # task in future
                if seconds_remaining < max_wait or max_wait == -1:
                    max_wait = seconds_remaining
            else:
                # task should be started
                task_thread = threading.Thread(target=schedule_tasks['datetime'][task_id]['function']).start()

                task_time = schedule_tasks['datetime'][task_id]['time']
                years   = task_time['years']
                months  = task_time['months']
                days    = task_time['days']
                hours   = task_time['hours']
                minutes = task_time['minutes']
                seconds = task_time['seconds']
                next_execution_time = get_next_execution_datetime(years, months, [], days, hours, minutes, seconds)

                tasks[task_id] = next_execution_time

                time_diff = next_execution_time - datetime.now()
                seconds_remaining = time_diff.total_seconds()

                if seconds_remaining > 0:
                    if seconds_remaining < max_wait or max_wait == -1:
                        max_wait = seconds_remaining

        with cond_obj:
            if max_wait > 0:
                cond_obj.wait(max_wait)
            else:
                cond_obj.wait()


# get_next_execution_datetime
#
# @desc     Calculates the next execution datetime given possible values for
#               year / month / ...
#
# @param    [int] years     Years.
# @param    [int] months    Months.
# @param    [int] weeks     Weeks.
# @param    [int] days      Days.
# @param    [int] hours     Hours.
# @param    [int] minutes   Minutes.
# @param    [int] seconds   Seconds.
#
# @info     Passing an empty list for a time parameter means all possible values
#               are allowed.
#
# @returns  datetime        Datetime object of the next execution time.
# @returns  None            None if no execution time in the future exists.
def get_next_execution_datetime(years, months, weeks, days, hours, minutes, seconds):
    now = datetime.now()

    if not years or years is None:
        years = list(range(now.year, now.year + 10))
    if not months or months is None:
        months = list(range(1, 13))
    if not days or days is None:
        days = list(range(1, 32))
    if not hours or hours is None:
        hours = list(range(0, 24))
    if not minutes or minutes is None:
        minutes = list(range(0, 60))
    if not seconds or seconds is None:
        seconds = list(range(0, 60))


    in_future = False

    # Go through all dates starting with the smallest one. Skip dates that are
    #     in the past and / or invalid. The first valid datetime is the next
    #     execution time.
    for i_year in range(0, len(years)):
        if i_year >= len(years):
            break
        if years[i_year] < now.year:
            continue

        if years[i_year] > now.year:
            in_future = True

        for i_month in range(0, len(months)):
            if i_month >= len(months):
                i_year += 1
                i_month = 0
                break
            if not in_future and months[i_month] < now.month:
                continue

            if not in_future and months[i_month] > now.month:
                in_future = True

            for i_day in range(0, len(days)):
                if i_day >= len(days):
                    i_month += 1
                    i_day = 0
                    break
                if days[i_day] > (lambda x: x[1])(monthrange(years[i_year], months[i_month])):
                    continue
                if not in_future and days[i_day] < now.day:
                    continue

                if not in_future and days[i_day] > now.day:
                    in_future = True

                for i_hour in range(0, len(hours)):
                    if i_hour >= len(hours):
                        i_day += 1
                        i_hour = 0
                        break
                    if not in_future and hours[i_hour] < now.hour:
                        continue

                    if not in_future and hours[i_hour] > now.hour:
                        in_future = True

                    for i_minute in range(0, len(minutes)):
                        if i_minute >= len(minutes):
                            i_hour += 1
                            i_minute = 0
                            break
                        if not in_future and minutes[i_minute] < now.minute:
                            continue

                        if not in_future and minutes[i_minute] > now.minute:
                            in_future = True

                        for i_second in range(0, len(seconds)):
                            if not in_future and seconds[i_second] <= now.second:
                                continue

                            year   = years[i_year]
                            month  = months[i_month]
                            day    = days[i_day]
                            hour   = hours[i_hour]
                            minute = minutes[i_minute]
                            second = seconds[i_second]

                            return datetime(year, month, day, hour, minute, second)

                        i_minute += 1
                    i_hour += 1
                i_day += 1
            i_month += 1
        i_year += 1

    # no execution time in the future
    return None


# datetime_schedule
#
# @desc     Executes the function 'function' at the given time(s). This will
#               create a new thread for each scheduling event.
#
# @param    labmda      function        Function to be executed.
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
#
# @raises   ValueError                  Raises a ValueError if the given task_id
#                                           is already in use.
def datetime_schedule(task_id, function, year, month, week, day, hour, minute, second, catchup = False, catchup_delay = None):
    global datetime_scheduler_cond
    global datetime_scheduler_thread
    global datetime_tasks_added
    global datetime_tasks_added_lock
    global schedule_tasks

    # Create and start the scheduling thread if it does not yet exist.
    if datetime_scheduler_thread is None:
        datetime_scheduler_thread = threading.Thread(target=datetime_scheduler_main, args=(datetime_scheduler_cond,)).start()


    scheduler = schedule_tasks['datetime']

    # Check if task_id is unused
    if task_id in scheduler:
        raise ValueError(f'Task-ID "{task_id}" is already in use!')

    # Convert time variables to lists, if necessary
    if year is None:
        years = []
    else:
        if isinstance(year, list):
            years = year
        else:
            years = [year]

    if month is None:
        months = []
    else:
        if isinstance(month, list):
            months = month
        else:
            months = [month]

    if week is None:
        weeks = []
    else:
        if isinstance(week, list):
            weeks = week
        else:
            weeks = [week]

    if day is None:
        days = []
    else:
        if isinstance(day, list):
            days = day
        else:
            days = [day]

    if hour is None:
        hours = []
    else:
        if isinstance(hour, list):
            hours = hour
        else:
            hours = [hour]

    if minute is None:
        minutes = []
    else:
        if isinstance(minute, list):
            minutes = minute
        else:
            minutes = [minute]

    if second is None:
        seconds = []
    else:
        if isinstance(second, list):
            seconds = second
        else:
            seconds = [second]

    next_execution_datetime = get_next_execution_datetime(years, months, weeks, days, hours, minutes, seconds)

    # add scheduling event to scheduler if it should be executed in the future
    if not next_execution_datetime is None:
        scheduler[task_id] = {
            'function' : function,
            'time'     : {
                'years'    : years,
                'months'   : months,
                'weeks'    : weeks,
                'days'     : days,
                'hours'    : hours,
                'minutes'  : minutes,
                'seconds'  : seconds
                }
            }

        datetime_tasks_added_lock.acquire()
        datetime_tasks_added.append(task_id)
        datetime_tasks_added_lock.release()

        with datetime_scheduler_cond:
            datetime_scheduler_cond.notify()


# TODO
#
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



# DEBUG: Test task. Can be removed after testing.
datetime_schedule('test_task', test_function, [], [], [], [], [], [], [], catchup = False, catchup_delay = None)
