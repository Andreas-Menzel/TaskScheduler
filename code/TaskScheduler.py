from calendar import monthrange
import threading
import json
from datetime import date, datetime, timedelta
import time
import os.path

import logHandler

logger = logHandler.getSimpleLogger(__name__, streamLogLevel=logHandler.DEBUG, fileLogLevel=logHandler.DEBUG)


# DEBUG: Test function. Can be removed after testing.
def test_function(task_id = None):
    #print(f'+ Started task {task_id}.')
    time.sleep(2)
    #print(f'- Stopped task {task_id}.')


file_execution_log = 'TaskScheduler_execution.log'
execution_log_write_interval = timedelta(seconds=5)
execution_log_thread = None
execution_log_thread_cond = threading.Condition()
# {
#     'datetime': { <task_id_1>: <last_execution_datetime>, ... }
#     'reccuring': { <task_id_1>: <last_execution_datetime>, ... }
# }
execution_log_data = { 'datetime': {}, 'reccuring': {} }
execution_log_data_changed = True
execution_log_data_lock = threading.Lock()


# This holds information about all tasks
schedule_tasks = { 'datetime': {}, 'reccuring': {'tasks': {}, 'groups': {}} }


# Condition and thread variables for the datetime scheduler
datetime_scheduler_cond = threading.Condition()
datetime_scheduler_thread = None

# New task ids will be added here. The datetime scheduler will then activate
#     these tasks according to the information in schedule_tasks.
datetime_tasks_added = []
datetime_tasks_added_lock = threading.Lock()


# Condition and thread variables for the reccuring scheduler
reccuring_scheduler_cond = threading.Condition()
reccuring_scheduler_thread = None

# New task ids will be added here. The reccuring scheduler will then activate
#     these tasks according to the information in schedule_tasks.
# [(<task_id>, <last_execution_datetime_or_None>), ...]
reccuring_tasks_added = []
reccuring_tasks_added_lock = threading.Lock()

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
reccuring_tasks_running = { 'tasks' : {}, 'groups' : {} }
reccuring_tasks_running_lock = threading.Lock()


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
    global execution_log_data
    global execution_log_data_changed
    global execution_log_data_lock
    global execution_log_thread_cond
    global datetime_tasks_added
    global datetime_tasks_added_lock
    global schedule_tasks
    global logger

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
                weeks   = task_time['weeks']
                days    = task_time['days']
                hours   = task_time['hours']
                minutes = task_time['minutes']
                seconds = task_time['seconds']
                next_execution_time = get_next_execution_datetime(years, months, weeks, days, hours, minutes, seconds)

                tasks[task] = next_execution_time

                logger.debug(f'Datetime scheduling task "{task}" was added recently. Added task to internal dictionary.')
            datetime_tasks_added = []
        datetime_tasks_added_lock.release()

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
                logger.info(f'Starting datetime-task "{task_id}".')
                task_information = schedule_tasks['datetime'][task_id]
                task_thread = threading.Thread(target=task_information['function'], args=(task_information['arguments']))
                task_thread.start()

                # Add function execution to execution log
                execution_log_data_lock.acquire()
                execution_log_data['datetime'][task_id] = datetime.now().isoformat()
                execution_log_data_changed = True
                execution_log_data_lock.release()

                # Notify execution logger
                with execution_log_thread_cond:
                    execution_log_thread_cond.notify()

                task_time = schedule_tasks['datetime'][task_id]['time']
                years   = task_time['years']
                months  = task_time['months']
                weeks   = task_time['weeks']
                days    = task_time['days']
                hours   = task_time['hours']
                minutes = task_time['minutes']
                seconds = task_time['seconds']
                next_execution_time = get_next_execution_datetime(years, months, weeks, days, hours, minutes, seconds)

                if not next_execution_time is None:
                    logger.debug(f'Next execution of datetime-task "{task_id}" is scheduled at {next_execution_time}.')

                    tasks[task_id] = next_execution_time

                    time_diff = next_execution_time - datetime.now()
                    seconds_remaining = time_diff.total_seconds()

                    if seconds_remaining > 0:
                        if seconds_remaining < max_wait or max_wait == -1:
                            max_wait = seconds_remaining
                else:
                    logger.info(f'Datetime-task "{task_id}" does not have an execution datetime in the future. Removing task.')

                    remove_tasks.append(task_id)

        for task_id in remove_tasks:
            del tasks[task_id]

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

                week_number = date(years[i_year], months[i_month], days[i_day]).isocalendar().week
                if not week_number in weeks:
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
    global datetime_scheduler_cond
    global datetime_scheduler_thread
    global datetime_tasks_added
    global datetime_tasks_added_lock
    global schedule_tasks
    global logger

    # Create and start the scheduling thread if it does not yet exist.
    if datetime_scheduler_thread is None:
        datetime_scheduler_thread = threading.Thread(target=datetime_scheduler_main, args=(datetime_scheduler_cond,))
        datetime_scheduler_thread.start()
        logger.debug('Created and started datetime_scheduler_thread.')


    scheduler = schedule_tasks['datetime']

    # Check if task_id is unused
    if task_id in scheduler:
        logger.critical(f'Datetime-Task-ID "{task_id}" is already in use!')
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

    next_execution_datetime = get_next_execution_datetime(years, months, weeks, days, hours, minutes, seconds)

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

        datetime_tasks_added_lock.acquire()
        datetime_tasks_added.append(task_id)
        datetime_tasks_added_lock.release()

        with datetime_scheduler_cond:
            datetime_scheduler_cond.notify()

        logger.info(f'Added datetime-task "{task_id}".')
    else:
        logger.info(f'Did not add datetime-task "{task_id}". No future execution datetime.')


# reccuring_scheduler_main
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
def reccuring_scheduler_main(cond_obj):
    global execution_log_data
    global execution_log_data_changed
    global execution_log_data_lock
    global reccuring_tasks_added
    global reccuring_tasks_added_lock
    global schedule_tasks
    global logging

    # <task_id> : <next_execution_time>
    all_tasks = {}

    # Wait for a task to be added
    with cond_obj:
        cond_obj.wait()

    while True:
        # check if new tasks were added
        reccuring_tasks_added_lock.acquire()
        if reccuring_tasks_added:
            for task, last_execution_datetime in reccuring_tasks_added:
                if last_execution_datetime is None:
                    next_execution_time = datetime.now()
                else:
                    next_execution_time = last_execution_datetime + schedule_tasks['reccuring']['tasks'][task]['timedelta']
                all_tasks[task] = next_execution_time

                logger.debug(f'Reccuring-task "{task}" was added recently. Added task to internal dictionary.')
            reccuring_tasks_added = []
        reccuring_tasks_added_lock.release()


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
                s_task = schedule_tasks['reccuring']['tasks'][task_id]
                for group in s_task['groups']:
                    group_priority = schedule_tasks['reccuring']['groups'][group]['priority']
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

        reccuring_tasks_running_lock.acquire()
        rtr = reccuring_tasks_running
        group_priorities_sorted = sorted(list(exec_tasks.keys()), reverse = True)
        for group_priority in group_priorities_sorted:
            groups = exec_tasks[group_priority]
            for group_id, group in groups.items():

                # Add group if not exist
                if not group_id in rtr['groups']:
                    rtr['groups'][group_id] = {}
                # Add currently_running if not exist
                if not 'currently_running' in rtr['groups'][group_id]:
                    rtr['groups'][group_id]['currently_running'] = 0

                # Check if another task can be started in this group
                group_currently_running = rtr['groups'][group_id]['currently_running']
                group_max_tasks = schedule_tasks['reccuring']['groups'][group_id]['max_tasks']
                if not group_max_tasks == -1 and group_currently_running >= group_max_tasks:
                    logger.info(f'Not starting reccuring-task. Already running maximum number of tasks in group "{group_id}": {group_currently_running} / {schedule_tasks["reccuring"]["groups"][group_id]["max_tasks"]}')
                    continue

                task_priorities_sorted = sorted(list(group.keys()), reverse = True)
                for task_priority in task_priorities_sorted:
                    tasks = group[task_priority]
                    for task in tasks:

                        # Add task if not exist
                        if not task in rtr['tasks']:
                            rtr['tasks'][task] = {}
                        # Add currently_running if not exist
                        if not 'currently_running' in rtr['tasks'][task]:
                            rtr['tasks'][task]['currently_running'] = 0

                        # Check if another instance of this task can be started
                        task_currently_running = rtr['tasks'][task]['currently_running']
                        task_max_instances = schedule_tasks['reccuring']['tasks'][task]['max_instances']
                        if not task_max_instances == -1 and task_currently_running >= task_max_instances:
                            logger.info(f'Not starting reccuring-task "{task}". Already running maximum number of instances: {task_max_instances}')
                            continue

                        # Increase running counter
                        rtr['tasks'][task]['currently_running'] += 1

                        # Add groups if not exist
                        for task_group in schedule_tasks['reccuring']['tasks'][task]['groups']:
                            if not task_group in rtr['groups']:
                                rtr['groups'][task_group] = {}
                            if not 'currently_running' in rtr['groups'][task_group]:
                                rtr['groups'][task_group]['currently_running'] = 0
                            rtr['groups'][task_group]['currently_running'] += 1


                        logger.info(f'Starting reccuring-task "{task}".')
                        task_information = schedule_tasks['reccuring']['tasks'][task]
                        task_thread = threading.Thread(target=reccuring_scheduler_execute_function, args=(  cond_obj,
                                                                                                            task, task_information['groups'],
                                                                                                            task_information['function'], task_information['arguments']))
                        task_thread.start()

                        # Add function execution to execution log
                        execution_log_data_lock.acquire()
                        execution_log_data['reccuring'][task] = datetime.now()
                        execution_log_data_changed = True
                        execution_log_data_lock.release()

                        # Notify execution logger
                        with execution_log_thread_cond:
                            execution_log_thread_cond.notify()

                        next_execution_time = datetime.now() + task_information['timedelta']
                        logger.debug(f'Next execution of reccuring-task "{task}" is scheduled at {next_execution_time}.')

                        all_tasks[task] = next_execution_time

                        time_diff = next_execution_time - datetime.now()
                        seconds_remaining = time_diff.total_seconds()

                        if seconds_remaining > 0:
                            if seconds_remaining < max_wait or max_wait == -1:
                                max_wait = seconds_remaining

        reccuring_tasks_running_lock.release()


        with cond_obj:
            if max_wait > 0:
                cond_obj.wait(max_wait)
            else:
                cond_obj.wait()


# reccuring_scheduler_execute_function
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
def reccuring_scheduler_execute_function(scheduler_cond, task_id, task_groups, function, arguments):
    global reccuring_tasks_running
    global reccuring_tasks_running_lock

    function(*arguments)

    # Decrease currently_running
    reccuring_tasks_running_lock.acquire()

    reccuring_tasks_running['tasks'][task_id]['currently_running'] -= 1

    for task_group in task_groups:
        reccuring_tasks_running['groups'][task_group]['currently_running'] -= 1

    reccuring_tasks_running_lock.release()

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
def reccuring_schedule(task_id, groups, function, arguments, timedelta, use_exec_log = True, max_instances = 1, priority = (0, 0)):
    global execution_log_data
    global reccuring_scheduler_cond
    global reccuring_scheduler_thread
    global reccuring_tasks_added
    global reccuring_tasks_added_lock
    global schedule_tasks
    global logger

    # Create and start the scheduling thread if it does not yet exist.
    if reccuring_scheduler_thread is None:
        reccuring_scheduler_thread = threading.Thread(target=reccuring_scheduler_main, args=(reccuring_scheduler_cond,))
        reccuring_scheduler_thread.start()
        logger.debug('Created and started reccuring_scheduler_thread.')

    scheduler = schedule_tasks['reccuring']['tasks']

    # Check if task_id is unused
    if task_id in scheduler:
        logger.critical(f'Reccuring-Task-ID "{task_id}" is already in use!')
        raise ValueError(f'Reccuring-Task-ID "{task_id}" is already in use!')

    scheduler[task_id] = {
        'groups'        : groups,
        'function'      : function,
        'arguments'     : arguments,
        'timedelta'     : timedelta,
        'max_instances' : max_instances,
        'priority'      : priority
        }

    logger.info(f'Added reccuring-task "{task_id}".')

    last_execution_datetime = None
    if use_exec_log:
        if task_id in execution_log_data['reccuring']:
            last_execution_datetime = datetime.fromisoformat(execution_log_data['reccuring'][task_id])

    reccuring_tasks_added_lock.acquire()
    reccuring_tasks_added.append((task_id, last_execution_datetime))
    reccuring_tasks_added_lock.release()

    # Create groups that do not exist
    for group in groups:
        if not group in schedule_tasks['reccuring']['groups']:
            set_reccuring_group(group, -1)

    with reccuring_scheduler_cond:
        reccuring_scheduler_cond.notify()


# reccuring_group
#
# @param    string      group_id        Group ID.
# @param    int         max_tasks       Maximum number of tasks allowed to run
#                                           simultaniously.
# @param    int         priority        Priority of the group. Prefer a group
#                                           with higher priority.
#
# @info     Set max_tasks = -1 for unlimited tasks.
def set_reccuring_group(group_id, max_tasks, priority = 0):
    global schedule_tasks
    global logger

    groups = schedule_tasks['reccuring']['groups']

    groups[group_id] = {
        'max_tasks' : max_tasks,
        'priority'  : priority
    }


def write_execution_log():
    global execution_log_data
    global execution_log_data_changed
    global execution_log_data_lock
    global execution_log_thread_cond
    global execution_log_write_interval
    global file_execution_log

    last_write = datetime.now()

    while True:
        # Check if execution_log_data has changed
        if not execution_log_data_changed:
            with execution_log_thread_cond:
                execution_log_thread_cond.wait()

        # Wait if new file write would be too soon
        if last_write + execution_log_write_interval > datetime.now():
            with execution_log_thread_cond:
                next_log_write = last_write + execution_log_write_interval
                max_wait = (next_log_write - datetime.now()).seconds
                if max_wait <= 0:
                    max_wait = 0.5
                execution_log_thread_cond.wait(max_wait)
                continue

        logger.debug('Writing execution-log to file.')

        execution_log_data_lock.acquire()
        with open(file_execution_log, 'w', encoding='utf-8') as file:
            json.dump(execution_log_data, file, ensure_ascii=False, indent=4, default=str)
        execution_log_data_changed = False
        execution_log_data_lock.release()

        last_write = datetime.now()

        with execution_log_thread_cond:
            execution_log_thread_cond.wait(execution_log_write_interval.seconds)


execution_log_thread = threading.Thread(target=write_execution_log)
execution_log_thread.start()

# Read initial execution log, if exists
if os.path.isfile(file_execution_log):
    with open(file_execution_log) as file:
        execution_log_data = json.load(file)

# DEBUG: Test task. Can be removed after testing.
datetime_schedule('DTS_test_task', test_function, [], [2022], [5], [], [27], [17], [59], [30, 31, 32, 33], catchup = False, catchup_delay = None)
#datetime_schedule('DTS_test_task2', test_function, [], [2020], [], [], [], [], [], [], catchup = False, catchup_delay = None)


# DEBUG: Test group
set_reccuring_group('group1', 2, priority = 0)

# DEBUG: Test task. Can be removed after testing.
#reccuring_schedule('RCS_test_task1', ['group1'], test_function, [], timedelta(seconds=1), True, 3, (10, 1))
#reccuring_schedule('RCS_test_task2', ['group1'], test_function, [], timedelta(seconds=5), True, 1, (10, 1))
#reccuring_schedule('test_task3', ['group2'], test_function, [], timedelta(seconds=7), True, 1, (10, 1))


#set_reccuring_group('small_backup', 2, priority = 0)
#
#reccuring_schedule('2_sec_backup', ['small_backup'], test_function, ['2_sec_backup'], timedelta(seconds=2), True, 1, (10, 1))
#
#reccuring_schedule('5_sec_backup', ['small_backup'], test_function, ['5_sec_backup'], timedelta(seconds=5))
#
## TODO: andere Reihenfolge?
#reccuring_schedule('5_sec_backup', test_function, timedelta(seconds=5), ['5_sec_backup'], ['small_backup'])
#reccuring_schedule('5_sec_backup', test_function, timedelta(seconds=5))
