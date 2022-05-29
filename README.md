# TaskScheduler

TaskScheduler is a Python script to execute planned and reccuring tasks.


## Usage

### Datetime tasks

Datetime tasks are used to execute functions at **fixed times**. These tasks
are implemented to be used similarly to cron-jobs.

Specify a list of years, months, weeks, days, hours, minutes and seconds to plan
the execution. Passing None or an empty list is interpreted as a wildcard
meaning all possible values.

TaskScheduler will create an execution-log containing the task id together with
the last time this task was started. The *datetime scheduler* can catch up on
missed tasks in case the script was not running on the specified execution time.
This feature is disabled by default. Check the *Function parameters* section
for more information on how to enable it.

#### Keep in mind

- A datetime task will call the given function with the given parameters.
  For each function call **a new thread is started**. Make sure that the
  function to be called is thread-safe.
- There is no limit for the maximum number of simultaneous task executions. Make
  sure that the function being called is able to
  **run multiple times at the same time**. Have a look at *reccuring tasks* if
  your task / a group of tasks must only run once at a time.

#### Function parameters

```
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
    ...
```

#### Examples

##### Simple server-side planning
```
import TaskScheduler

def backup():
    # make backup
    print('Backup finished.')

# Start backup every day at 3:00 AM
datetime_schedule('dailyBackup', backup, [], None, None, None, None, 3, 0, 0)

# Start backup every day at 3:00 AM if month is between January and April
datetime_schedule('dailyBackupJanToApr', backup, [], None, [1, 2, 3, 4], None, None, 3, 0, 0)

# Start backup on the first day of every month at 3:00 AM
datetime_schedule('monthlyBackup', backup, [], None, None, None, 1, 3, 0, 0)
```

##### Simple laptop-side planning
```
import TaskScheduler

def backup():
    # make backup
    print('Backup finished.')

# Start backup every day at 3:00 AM.
# If the laptop was turned off at 3:00 AM, start the backup when starting the
#     script with a delay between 30 seconds and 5 minutes.
datetime_schedule('dailyBackup', backup, [], None, None, None, None, 3, 0, 0, True, (30, 300))
```

### Reccuring tasks

Reccuring tasks are used to execute functions at **fixed intervals**.

It is possible to group and prioritize tasks. Entire groups can also be
prioritized.

TaskScheduler will create an execution-log containing the task id together with
the last time this task was started. The *reccuring scheduler* can catch up on
missed tasks in case the script was not running on the specified execution time.
This feature is disabled by default. Check the *Function parameters* section
for more information on how to enable it.

#### Keep in mind

- A reccuring task will call the given function with the given parameters.
  For each function call **a new thread is started**. Make sure that the
  function to be called is thread-safe.

#### Function parameters

```
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
    ...
```

```
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
    ...
```

#### Examples

##### Simple reccuring scheduling
```
def func():
    print('Function started.')

# Execute a function every minute
reccuring_schedule('task_1', [], func, [], timedelta(seconds=60))
```

##### More complex backup strategy
Start the following (incremental) backups:
- *5min* interval
- *10min* interval
- *30min* interval
- *1hour* interval
- *1day* interval
- *1month* interval
- *1year* interval

with the following conditions:
- each backup must only run once at a time
- no more than 2 "short-term backups" (*5min*, *10min*, *30min*) may run at the
  same time
- no more than 2 "mid-term backups" (*1hour*, *1day*) may run at the same time
- no more than 1 "long-term backup" (*1month*, *1year*) may run at the same time
- no more than 4 backups may run at the same time
- catch up on missed backup executions for "long-term backups"
- always choose "long-term" over "mid-term" over "short-term"
- always choose *5min* over *10min* over *30min*
- always choose *1year* over *1month*
- prefer *1hour* over *1day*
- if *1day* is overdue more than 3 hours, prefer it over *1hour*

```
def backup(increment):
    # make backup
    print(f'Backup "{increment}" finished')


set_reccuring_group('backups', 4, priority = 0)

# "short-term" backups
set_reccuring_group('short_term', 2, priority = 1)
reccuring_schedule('backup_5min', ['backups', 'short_term'], backup, ['5min'], timedelta(seconds=60*5), priority=(2,0))
reccuring_schedule('backup_10min', ['backups', 'short_term'], backup, ['10min'], timedelta(seconds=60*10), priority=(1,0))
reccuring_schedule('backup_30min', ['backups', 'short_term'], backup, ['30min'], timedelta(seconds=60*30), priority=(0,0))

# "mid-term" backups
set_reccuring_group('mid_term', 2, priority = 2)
reccuring_schedule('backup_1hour', ['backups', 'mid_term'], backup, ['1hour'], timedelta(seconds=60*60), priority=(60*60*3,0))
reccuring_schedule('backup_1day', ['backups', 'mid_term'], backup, ['1day'], timedelta(seconds=60*60*24), priority=(0,1))

# "long-term" backups
set_reccuring_group('long_term', 1, priority = 3)
reccuring_schedule('backup_1month', ['backups', 'long_term'], backup, ['1month'], timedelta(seconds=60*60*24*30), priority=(0,0), use_exec_log = True)
reccuring_schedule('backup_1year', ['backups', 'long_term'], backup, ['1year'], timedelta(seconds=60*60*24*365), priority=(1,0), use_exec_log = True)
```


## Used modules

For logging I use tizianerlenbergs [logHandler.py](https://github.com/tizianerlenberg/multiSSH/blob/6f48a3a5d0542fcb61682b9cb835b769b60e406b/logHandler.py) from his [multiSSH](https://github.com/tizianerlenberg/multiSSH) repository.
