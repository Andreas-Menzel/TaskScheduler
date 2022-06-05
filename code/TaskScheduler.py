from calendar import monthrange
from datetime import date, datetime, timedelta
import json
import os.path
import threading
import time

import logHandler

_LOGGER = logHandler.getSimpleLogger(__name__, streamLogLevel=logHandler.DEBUG, fileLogLevel=logHandler.DEBUG)


_FILE_EXECUTION_LOG = 'TaskScheduler_execution.log'
_EXECUTION_LOG_WRITE_INTERVAL = timedelta(seconds=5)
_EXECUTION_LOG_THREAD = None
_EXECUTION_LOG_THREAD_COND = threading.Condition()
# {
#     'datetime': { <task_id_1>: <last_execution_datetime>, ... }
#     'reccuring': { <task_id_1>: <last_execution_datetime>, ... }
# }
_EXECUTION_LOG_DATA = { 'datetime': {}, 'reccuring': {} }
_EXECUTION_LOG_DATA_CHANGED = True
_EXECUTION_LOG_DATA_LOCK = threading.Lock()


# {
#     'datetime': {
#         <task_id_1>: {
#             'function' : <function>,
#             'arguments': <arguments>,
#             'time'     : {
#                 'years'    : <years>,
#                 'months'   : <months>,
#                 'weeks'    : <weeks>,
#                 'days'     : <days>,
#                 'hours'    : <hours>,
#                 'minutes'  : <minutes>,
#                 'seconds'  : <second>
#                 }
#         }, ...
#     },
#     'reccuring': {
#         'tasks': {
#             <task_id_1>: {
#                 'groups'        : groups,
#                 'function'      : function,
#                 'arguments'     : arguments,
#                 'timedelta'     : timedelta,
#                 'max_instances' : max_instances,
#                 'priority'      : priority
#             }, ...
#         },
#         'groups': {
#             <group_id_1>: {
#                 'max_tasks' : max_tasks,
#                 'priority'  : priority
#             }, ...
#         }
#     }
# }
_SCHEDULE_TASKS = { 'datetime': {}, 'reccuring': {'tasks': {}, 'groups': {}} }


# Condition and thread variables for the datetime scheduler
_DATETIME_SCHEDULER_COND = threading.Condition()
_DATETIME_SCHEDULER_THREAD = None

# New task ids will be added here. The datetime scheduler will then activate
#     these tasks according to the information in schedule_tasks.
# {
#     (<task_id_1>, <next_execution_time>), ...
# }
_DATETIME_TASKS_ADDED = []
_DATETIME_TASKS_ADDED_LOCK = threading.Lock()


# Condition and thread variables for the reccuring scheduler
_RECCURING_SCHEDULER_COND = threading.Condition()
_RECCURING_SCHEDULER_THREAD = None

# New task ids will be added here. The reccuring scheduler will then activate
#     these tasks according to the information in schedule_tasks.
# [(<task_id>, <last_execution_datetime_or_None>), ...]
_RECCURING_TASKS_ADDED = []
_RECCURING_TASKS_ADDED_LOCK = threading.Lock()

# {
#     'tasks' : {
#         <task_id> : {
#             'currently_running' : <num_active_threads>,
#             TODO: threads: ...
#         }, ...
#     }
#     'groups' : {
#         <group_id> : {
#             'currently_running' : <num_active_threads>
#         }, ...
#     }
# }
_RECCURING_TASKS_RUNNING = { 'tasks' : {}, 'groups' : {} }
_RECCURING_TASKS_RUNNING_LOCK = threading.Lock()


# _datetime_scheduler_main
#
# @desc     This function will start the datetime tasks.
#
# @param    Condition() cond_obj    A threading condition object to manage
#                                       wait() and notify().
#
# @note     Since this function uses wait() and relies on being notify()ed, it
#               has to be executed in a seperate thread. Use notify() whenever a
#               new task is added.
def _datetime_scheduler_main(cond_obj):
    global _EXECUTION_LOG_DATA
    global _EXECUTION_LOG_DATA_CHANGED
    global _EXECUTION_LOG_DATA_LOCK
    global _EXECUTION_LOG_THREAD_COND
    global _DATETIME_TASKS_ADDED
    global _DATETIME_TASKS_ADDED_LOCK
    global _SCHEDULE_TASKS
    global _LOGGER

    # <task_id> : <next_execution_time>
    tasks = {}

    # Wait for a task to be added
    with cond_obj:
        cond_obj.wait()

    while True:
        # check if new tasks were added
        _DATETIME_TASKS_ADDED_LOCK.acquire()
        if _DATETIME_TASKS_ADDED:
            for task, next_execution_time in _DATETIME_TASKS_ADDED:
                task_time = _SCHEDULE_TASKS['datetime'][task]['time']
                years   = task_time['years']
                months  = task_time['months']
                weeks   = task_time['weeks']
                days    = task_time['days']
                hours   = task_time['hours']
                minutes = task_time['minutes']
                seconds = task_time['seconds']

                tasks[task] = next_execution_time

                _LOGGER.debug(f'Datetime scheduling task "{task}" was added recently. Added task to internal dictionary.')
            _DATETIME_TASKS_ADDED = []
        _DATETIME_TASKS_ADDED_LOCK.release()

        # get next task and execution time (seconds remaining) and start tasks
        remove_tasks = []
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
                _LOGGER.info(f'Starting datetime-task "{task_id}".')
                task_information = _SCHEDULE_TASKS['datetime'][task_id]
                task_thread = threading.Thread(target=task_information['function'], args=(task_information['arguments']))
                task_thread.start()

                # Add function execution to execution log
                _EXECUTION_LOG_DATA_LOCK.acquire()
                _EXECUTION_LOG_DATA['datetime'][task_id] = datetime.now().isoformat()
                _EXECUTION_LOG_DATA_CHANGED = True
                _EXECUTION_LOG_DATA_LOCK.release()

                # Notify execution logger
                with _EXECUTION_LOG_THREAD_COND:
                    _EXECUTION_LOG_THREAD_COND.notify()

                task_time = _SCHEDULE_TASKS['datetime'][task_id]['time']
                years   = task_time['years']
                months  = task_time['months']
                weeks   = task_time['weeks']
                days    = task_time['days']
                hours   = task_time['hours']
                minutes = task_time['minutes']
                seconds = task_time['seconds']
                next_execution_time = _get_next_execution_datetime(years, months, weeks, days, hours, minutes, seconds)

                if not next_execution_time is None:
                    _LOGGER.debug(f'Next execution of datetime-task "{task_id}" is scheduled at {next_execution_time}.')

                    tasks[task_id] = next_execution_time

                    time_diff = next_execution_time - datetime.now()
                    seconds_remaining = time_diff.total_seconds()

                    if seconds_remaining > 0:
                        if seconds_remaining < max_wait or max_wait == -1:
                            max_wait = seconds_remaining
                else:
                    _LOGGER.info(f'Datetime-task "{task_id}" does not have an execution datetime in the future. Removing task.')

                    remove_tasks.append(task_id)

        for task_id in remove_tasks:
            del tasks[task_id]

        with cond_obj:
            if max_wait > 0:
                cond_obj.wait(max_wait)
            else:
                cond_obj.wait()


# _get_next_execution_datetime
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
# @param    bool  reverse   Reversed search.
#
# @info     Passing an empty list for a time parameter means all possible values
#               are allowed.
#
# @returns  datetime        Datetime object of the next execution time.
# @returns  None            None if no execution time in the future exists.
def _get_next_execution_datetime(years, months, weeks, days, hours, minutes, seconds, reverse = False):
    now = datetime.now()

    if not years or years is None:
        years = list(range(now.year, now.year + 10))
    if not months or months is None:
        months = list(range(1, 13))
    if not weeks or weeks is None:
        weeks = list(range(1, 54))
    if not days or days is None:
        days = list(range(1, 32))
    if not hours or hours is None:
        hours = list(range(0, 24))
    if not minutes or minutes is None:
        minutes = list(range(0, 60))
    if not seconds or seconds is None:
        seconds = list(range(0, 60))


    range_years   = range(0, len(years))
    range_months  = range(0, len(months))
    range_days    = range(0, len(days))
    range_hours   = range(0, len(hours))
    range_minutes = range(0, len(minutes))
    range_seconds = range(0, len(seconds))

    if reverse:
        range_years   = reversed(range_years)
        range_months  = reversed(range_months)
        range_days    = reversed(range_days)
        range_hours   = reversed(range_hours)
        range_minutes = reversed(range_minutes)
        range_seconds = reversed(range_seconds)


    in_future = False   # for standard forward search
    in_past = False     # for reversed search

    # Go through all dates starting with the smallest one. Skip dates that are
    #     in the past and / or invalid. The first valid datetime is the next
    #     execution time.
    for i_year in range_years:
        if i_year >= len(years):
            break
        if not reverse:
            if years[i_year] < now.year:
                continue
        else:
            if years[i_year] > now.year:
                continue

        if not reverse:
            if years[i_year] > now.year:
                in_future = True
        else:
            if years[i_year] < now.year:
                in_past = True

        for i_month in range_months:
            if i_month >= len(months):
                i_year += 1
                i_month = 0
                break
            if not reverse:
                if not in_future and months[i_month] < now.month:
                    continue
            else:
                if not in_past and months[i_month] > now.month:
                    continue

            if not reverse:
                if not in_future and months[i_month] > now.month:
                    in_future = True
            else:
                if not in_past and months[i_month] < now.month:
                    in_past = True

            for i_day in range_days:
                if i_day >= len(days):
                    i_month += 1
                    i_day = 0
                    break
                if days[i_day] > (lambda x: x[1])(monthrange(years[i_year], months[i_month])):
                    continue

                if not reverse:
                    if not in_future and days[i_day] < now.day:
                        continue
                else:
                    if not in_past and days[i_day] > now.day:
                        continue

                week_number = date(years[i_year], months[i_month], days[i_day]).isocalendar().week
                if not week_number in weeks:
                    continue

                if not reverse:
                    if not in_future and days[i_day] > now.day:
                        in_future = True
                else:
                    if not in_past and days[i_day] < now.day:
                        in_past = True

                for i_hour in range_hours:
                    if i_hour >= len(hours):
                        i_day += 1
                        i_hour = 0
                        break

                    if not reverse:
                        if not in_future and hours[i_hour] < now.hour:
                            continue
                    else:
                        if not in_past and hours[i_hour] > now.hour:
                            continue

                    if not reverse:
                        if not in_future and hours[i_hour] > now.hour:
                            in_future = True
                    else:
                        if not in_past and hours[i_hour] < now.hour:
                            in_past = True

                    for i_minute in range_minutes:
                        if i_minute >= len(minutes):
                            i_hour += 1
                            i_minute = 0
                            break

                        if not reverse:
                            if not in_future and minutes[i_minute] < now.minute:
                                continue
                        else:
                            if not in_past and minutes[i_minute] > now.minute:
                                continue

                        if not reverse:
                            if not in_future and minutes[i_minute] > now.minute:
                                in_future = True
                        else:
                            if not in_past and minutes[i_minute] < now.minute:
                                in_past = True

                        for i_second in range_seconds:
                            if not reverse:
                                if not in_future and seconds[i_second] <= now.second:
                                    continue
                            else:
                                if not in_past and seconds[i_second] >= now.second:
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
# @param    string      task_id         Task identifier.
#
# @param    labmda      function        Function to be executed.
# @param    []          arguments       Arguments for the function.
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
def datetime_schedule(task_id, function, arguments, year, month, week, day, hour, minute, second, catchup = False, catchup_delay = None):
    global _DATETIME_SCHEDULER_COND
    global _DATETIME_SCHEDULER_THREAD
    global _DATETIME_TASKS_ADDED
    global _DATETIME_TASKS_ADDED_LOCK
    global _EXECUTION_LOG_DATA
    global _SCHEDULE_TASKS
    global _LOGGER

    # Create and start the scheduling thread if it does not yet exist.
    if _DATETIME_SCHEDULER_THREAD is None:
        _DATETIME_SCHEDULER_THREAD = threading.Thread(target=_datetime_scheduler_main, args=(_DATETIME_SCHEDULER_COND,))
        _DATETIME_SCHEDULER_THREAD.start()
        _LOGGER.debug('Created and started _DATETIME_SCHEDULER_THREAD.')


    scheduler = _SCHEDULE_TASKS['datetime']

    # Check if task_id is unused
    if task_id in scheduler:
        _LOGGER.critical(f'Datetime-Task-ID "{task_id}" is already in use!')
        raise ValueError(f'Datetime-Task-ID "{task_id}" is already in use!')

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


    next_execution_datetime = None
    if catchup:
        if task_id in _EXECUTION_LOG_DATA['datetime']:
            last_execution_datetime = datetime.fromisoformat(_EXECUTION_LOG_DATA['datetime'][task_id])
            if last_execution_datetime < _get_next_execution_datetime(years, months, weeks, days, hours, minutes, seconds, reverse=True):
                next_execution_datetime = datetime.now()

    if next_execution_datetime is None:
        next_execution_datetime = _get_next_execution_datetime(years, months, weeks, days, hours, minutes, seconds)
        _LOGGER.warning('Executing as planned.')

    # add scheduling event to scheduler if it should be executed in the future
    if not next_execution_datetime is None:
        scheduler[task_id] = {
            'function'  : function,
            'arguments' : arguments,
            'time'      : {
                'years'    : years,
                'months'   : months,
                'weeks'    : weeks,
                'days'     : days,
                'hours'    : hours,
                'minutes'  : minutes,
                'seconds'  : seconds
                }
            }

        _DATETIME_TASKS_ADDED_LOCK.acquire()
        _DATETIME_TASKS_ADDED.append((task_id, next_execution_datetime))
        _DATETIME_TASKS_ADDED_LOCK.release()

        with _DATETIME_SCHEDULER_COND:
            _DATETIME_SCHEDULER_COND.notify()

        _LOGGER.info(f'Added datetime-task "{task_id}".')
    else:
        _LOGGER.info(f'Did not add datetime-task "{task_id}". No future execution datetime.')


# _reccuring_scheduler_main
#
# @desc     This function will start the reccuring tasks.
#
# @param    Condition() cond_obj    A threading condition object to manage
#                                       wait() and notify().
#
# @note     Since this function uses wait() and relies on being notify()ed, it
#               has to be executed in a seperate thread. Use notify() whenever a
#               new task is added.
# @note     The first execution of function will be immediately after calling
#               this function.
def _reccuring_scheduler_main(cond_obj):
    global _EXECUTION_LOG_DATA
    global _EXECUTION_LOG_DATA_CHANGED
    global _EXECUTION_LOG_DATA_LOCK
    global _RECCURING_TASKS_ADDED
    global _RECCURING_TASKS_ADDED_LOCK
    global _SCHEDULE_TASKS
    global logging

    # <task_id> : <next_execution_time>
    all_tasks = {}

    # Wait for a task to be added
    with cond_obj:
        cond_obj.wait()

    while True:
        # check if new tasks were added
        _RECCURING_TASKS_ADDED_LOCK.acquire()
        if _RECCURING_TASKS_ADDED:
            for task, last_execution_datetime in _RECCURING_TASKS_ADDED:
                if last_execution_datetime is None:
                    next_execution_time = datetime.now()
                else:
                    next_execution_time = last_execution_datetime + _SCHEDULE_TASKS['reccuring']['tasks'][task]['timedelta']
                all_tasks[task] = next_execution_time

                _LOGGER.debug(f'Reccuring-task "{task}" was added recently. Added task to internal dictionary.')
            _RECCURING_TASKS_ADDED = []
        _RECCURING_TASKS_ADDED_LOCK.release()


        # for all tasks:
        #     get next max_wait
        #     if next_execution_time <= 0:
        #         exec_tasks[group_id] = [task_id_1, ...]
        # for all groups sorted by priority high to low:
        #     if not num_tasks < max_tasks:
        #         continue
        #     for all tasks in group sorted by high to low:
        #         if num_tasks < max_tasks AND num_instances < max_instances:
        #             start task

        # {
        #     <group_priority> : {
        #         <group_id> : {
        #             <task_priority> : [
        #                 <task_id_1>, ...
        #             ], ...
        #         }
        #     }, ...
        # }
        exec_tasks = {}

        # get next task and execution time (seconds remaining) and start tasks
        max_wait = -1
        for task_id, task in all_tasks.items():
            time_diff = task - datetime.now()
            seconds_remaining = time_diff.total_seconds()

            if seconds_remaining > 0:
                # task in future
                if seconds_remaining < max_wait or max_wait == -1:
                    max_wait = seconds_remaining
            else:
                # task should be started
                s_task = _SCHEDULE_TASKS['reccuring']['tasks'][task_id]
                for group in s_task['groups']:
                    group_priority = _SCHEDULE_TASKS['reccuring']['groups'][group]['priority']
                    task_priority_static, task_priority_dynamic = s_task['priority']
                    task_priority = task_priority_static + (seconds_remaining * -1) * task_priority_dynamic

                    # create group_priority entry if not exist
                    if not group_priority in exec_tasks:
                        exec_tasks[group_priority] = {}
                    # create group entry if not exist
                    if not group in exec_tasks[group_priority]:
                        exec_tasks[group_priority][group] = {}
                    # create task_priority entry if not exist
                    if not task_priority in exec_tasks[group_priority][group]:
                        exec_tasks[group_priority][group][task_priority] = []
                    # add task
                    exec_tasks[group_priority][group][task_priority].append(task_id)

        _RECCURING_TASKS_RUNNING_LOCK.acquire()
        rtr = _RECCURING_TASKS_RUNNING
        group_priorities_sorted = sorted(list(exec_tasks.keys()), reverse = True)
        # All tasks that are started will be added here so a task is not started
        #     multiple times if it is in multiple groups.
        tasks_started = []
        for group_priority in group_priorities_sorted:
            groups = exec_tasks[group_priority]
            for group_id, group in groups.items():

                # Check if another task can be started in this group
                group_currently_running = rtr['groups'][group_id]['currently_running']
                group_max_tasks = _SCHEDULE_TASKS['reccuring']['groups'][group_id]['max_tasks']
                if not group_max_tasks == -1 and group_currently_running >= group_max_tasks:
                    _LOGGER.info(f'Not starting reccuring-task. Already running maximum number of tasks in group "{group_id}": {group_currently_running} / {_SCHEDULE_TASKS["reccuring"]["groups"][group_id]["max_tasks"]}')
                    continue

                task_priorities_sorted = sorted(list(group.keys()), reverse = True)
                for task_priority in task_priorities_sorted:
                    tasks = group[task_priority]
                    for task in tasks:

                        # Check if task has already been started
                        if task in tasks_started:
                            continue

                        # Check if another instance of this task can be started
                        task_currently_running = rtr['tasks'][task]['currently_running']
                        task_max_instances = _SCHEDULE_TASKS['reccuring']['tasks'][task]['max_instances']
                        if not task_max_instances == -1 and task_currently_running >= task_max_instances:
                            _LOGGER.info(f'Not starting reccuring-task "{task}". Already running maximum number of instances: {task_max_instances}')
                            continue

                        # Check if all groups of this task have free capacity
                        enough_capacity = True
                        s_task = _SCHEDULE_TASKS['reccuring']['tasks'][task_id]
                        for task_group_id in s_task['groups']:
                            task_group_currently_running = rtr['groups'][task_group_id]['currently_running']
                            task_group_max_tasks = _SCHEDULE_TASKS['reccuring']['groups'][task_group_id]['max_tasks']
                            if not task_group_max_tasks == -1 and task_group_currently_running >= task_group_max_tasks:
                                enough_capacity = False
                                break
                        if not enough_capacity:
                            continue

                        # Increase running counter
                        rtr['tasks'][task]['currently_running'] += 1
                        for task_group in _SCHEDULE_TASKS['reccuring']['tasks'][task]['groups']:
                            rtr['groups'][task_group]['currently_running'] += 1


                        _LOGGER.info(f'Starting reccuring-task "{task}".')
                        tasks_started.append(task)
                        task_information = _SCHEDULE_TASKS['reccuring']['tasks'][task]
                        task_thread = threading.Thread(target=_reccuring_scheduler_execute_function, args=(  cond_obj,
                                                                                                            task, task_information['groups'],
                                                                                                            task_information['function'], task_information['arguments']))
                        task_thread.start()

                        # Add function execution to execution log
                        _EXECUTION_LOG_DATA_LOCK.acquire()
                        _EXECUTION_LOG_DATA['reccuring'][task] = datetime.now()
                        _EXECUTION_LOG_DATA_CHANGED = True
                        _EXECUTION_LOG_DATA_LOCK.release()

                        # Notify execution logger
                        with _EXECUTION_LOG_THREAD_COND:
                            _EXECUTION_LOG_THREAD_COND.notify()

                        next_execution_time = datetime.now() + task_information['timedelta']
                        _LOGGER.debug(f'Next execution of reccuring-task "{task}" is scheduled at {next_execution_time}.')

                        all_tasks[task] = next_execution_time

                        time_diff = next_execution_time - datetime.now()
                        seconds_remaining = time_diff.total_seconds()

                        if seconds_remaining > 0:
                            if seconds_remaining < max_wait or max_wait == -1:
                                max_wait = seconds_remaining

        _RECCURING_TASKS_RUNNING_LOCK.release()


        with cond_obj:
            if max_wait > 0:
                cond_obj.wait(max_wait)
            else:
                cond_obj.wait()


# _reccuring_scheduler_execute_function
#
# @desc Calls the function with the arguments.
#
# @param    Condition   scheduler_cond  Scheduler condition object. This will
#                                           be used to notify() the scheduler
#                                           thread after the function was
#                                           executed.
#
# @param    string      task_id         ID of the task.
#
# @param    labmda      function        Function to be executed.
# @param    []          arguments       Arguments for the function.
#
# @param    Lock()      task_lock
def _reccuring_scheduler_execute_function(scheduler_cond, task_id, task_groups, function, arguments):
    global _RECCURING_TASKS_RUNNING
    global _RECCURING_TASKS_RUNNING_LOCK

    function(*arguments)

    # Decrease currently_running
    _RECCURING_TASKS_RUNNING_LOCK.acquire()

    _RECCURING_TASKS_RUNNING['tasks'][task_id]['currently_running'] -= 1

    for task_group in task_groups:
        _RECCURING_TASKS_RUNNING['groups'][task_group]['currently_running'] -= 1

    _RECCURING_TASKS_RUNNING_LOCK.release()

    with scheduler_cond:
        scheduler_cond.notify()


# reccuring_schedule
#
# @desc     Executes the function 'function' every delay seconds.
#
# @param    string      task_id         Task identifier.
# @param    [string]    groups          Groups the task is part of.
#
# @param    labmda      function        Function to be executed.
# @param    []          arguments       Arguments for the function.
#
# @param    int         timedelta       "Delay".
#
# @param    bool        use_exec_log    If True, will check the execution log
#                                           to calculate the first execution
#                                           datetime.
#
# @param    int         max_instances   Maximum number of instances of the
#                                           function running simultaniously.
# @param    (int, int)  priority        Priority of the task. The first value
#                                           is the "fixed" priority. The second
#                                           value will be multiplied with the
#                                           number of second the task is
#                                           overdue.
#
# @info     total_priority = first_val + <seconds_overdue> * second_val
def reccuring_schedule(task_id, groups, function, arguments, timedelta, use_exec_log = False, max_instances = 1, priority = (0, 0)):
    global _EXECUTION_LOG_DATA
    global _RECCURING_SCHEDULER_COND
    global _RECCURING_SCHEDULER_THREAD
    global _RECCURING_TASKS_ADDED
    global _RECCURING_TASKS_ADDED_LOCK
    global _RECCURING_TASKS_RUNNING
    global _RECCURING_TASKS_RUNNING_LOCK
    global _SCHEDULE_TASKS
    global _LOGGER

    if groups == []:
        groups = [f'#DEFAULT_GROUP#{task_id}#']

    scheduler = _SCHEDULE_TASKS['reccuring']['tasks']

    # Check if task_id is unused
    if task_id in scheduler:
        _LOGGER.critical(f'Reccuring-Task-ID "{task_id}" is already in use!')
        raise ValueError(f'Reccuring-Task-ID "{task_id}" is already in use!')

    # Create and start the scheduling thread if it does not yet exist.
    if _RECCURING_SCHEDULER_THREAD is None:
        _RECCURING_SCHEDULER_THREAD = threading.Thread(target=_reccuring_scheduler_main, args=(_RECCURING_SCHEDULER_COND,))
        _RECCURING_SCHEDULER_THREAD.start()
        _LOGGER.debug('Created and started _RECCURING_SCHEDULER_THREAD.')

    scheduler[task_id] = {
        'groups'        : groups,
        'function'      : function,
        'arguments'     : arguments,
        'timedelta'     : timedelta,
        'max_instances' : max_instances,
        'priority'      : priority
        }

    _LOGGER.info(f'Added reccuring-task "{task_id}".')

    last_execution_datetime = None
    if use_exec_log:
        if task_id in _EXECUTION_LOG_DATA['reccuring']:
            last_execution_datetime = datetime.fromisoformat(_EXECUTION_LOG_DATA['reccuring'][task_id])

    _RECCURING_TASKS_ADDED_LOCK.acquire()
    _RECCURING_TASKS_ADDED.append((task_id, last_execution_datetime))
    _RECCURING_TASKS_ADDED_LOCK.release()

    # Create groups that do not exist
    for group in groups:
        if not group in _SCHEDULE_TASKS['reccuring']['groups']:
            set_reccuring_group(group, -1)

    with _RECCURING_TASKS_RUNNING_LOCK:
        # Add task to _RECCURING_TASKS_RUNNING if not exist
        if not task_id in _RECCURING_TASKS_RUNNING['tasks']:
            _RECCURING_TASKS_RUNNING['tasks'][task_id] = {}
        # Add currently_running if not exist
        if not 'currently_running' in _RECCURING_TASKS_RUNNING['tasks'][task_id]:
            _RECCURING_TASKS_RUNNING['tasks'][task_id]['currently_running'] = 0

    with _RECCURING_SCHEDULER_COND:
        _RECCURING_SCHEDULER_COND.notify()


# set_reccuring_group
#
# @param    string      group_id        Group ID.
# @param    int         max_tasks       Maximum number of tasks allowed to run
#                                           simultaniously.
# @param    int         priority        Priority of the group. Prefer a group
#                                           with higher priority.
#
# @info     Set max_tasks = -1 for unlimited tasks.
def set_reccuring_group(group_id, max_tasks, priority = 0):
    global _SCHEDULE_TASKS
    global _LOGGER
    global _RECCURING_TASKS_RUNNING
    global _RECCURING_TASKS_RUNNING_LOCK

    # Set group attributes
    groups = _SCHEDULE_TASKS['reccuring']['groups']
    groups[group_id] = {
        'max_tasks' : max_tasks,
        'priority'  : priority
    }

    with _RECCURING_TASKS_RUNNING_LOCK:
        # Add group to _RECCURING_TASKS_RUNNING if not exist
        if not group_id in _RECCURING_TASKS_RUNNING['groups']:
            _RECCURING_TASKS_RUNNING['groups'][group_id] = {}
        # Add currently_running if not exist
        if not 'currently_running' in _RECCURING_TASKS_RUNNING['groups'][group_id]:
            _RECCURING_TASKS_RUNNING['groups'][group_id]['currently_running'] = 0


def _write_execution_log():
    global _EXECUTION_LOG_DATA
    global _EXECUTION_LOG_DATA_CHANGED
    global _EXECUTION_LOG_DATA_LOCK
    global _EXECUTION_LOG_THREAD_COND
    global _EXECUTION_LOG_WRITE_INTERVAL
    global _FILE_EXECUTION_LOG

    last_write = datetime.now()

    while True:
        # Check if execution_log_data has changed
        if not _EXECUTION_LOG_DATA_CHANGED:
            with _EXECUTION_LOG_THREAD_COND:
                _EXECUTION_LOG_THREAD_COND.wait()

        # Wait if new file write would be too soon
        if last_write + _EXECUTION_LOG_WRITE_INTERVAL > datetime.now():
            with _EXECUTION_LOG_THREAD_COND:
                next_log_write = last_write + _EXECUTION_LOG_WRITE_INTERVAL
                max_wait = (next_log_write - datetime.now()).seconds
                if max_wait <= 0:
                    max_wait = 0.5
                _EXECUTION_LOG_THREAD_COND.wait(max_wait)
                continue

        _LOGGER.debug('Writing execution-log to file.')

        _EXECUTION_LOG_DATA_LOCK.acquire()
        with open(_FILE_EXECUTION_LOG, 'w', encoding='utf-8') as file:
            json.dump(_EXECUTION_LOG_DATA, file, ensure_ascii=False, indent=4, default=str)
        _EXECUTION_LOG_DATA_CHANGED = False
        _EXECUTION_LOG_DATA_LOCK.release()

        last_write = datetime.now()

        with _EXECUTION_LOG_THREAD_COND:
            _EXECUTION_LOG_THREAD_COND.wait(_EXECUTION_LOG_WRITE_INTERVAL.seconds)


_EXECUTION_LOG_THREAD = threading.Thread(target=_write_execution_log)
_EXECUTION_LOG_THREAD.start()

# Read initial execution log, if exists
if os.path.isfile(_FILE_EXECUTION_LOG):
    with open(_FILE_EXECUTION_LOG) as file:
        _EXECUTION_LOG_DATA = json.load(file)
