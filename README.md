# TaskScheduler

TaskScheduler is a Python script to execute planned and reccuring tasks.


## Usage

### Datetime tasks

Datetime tasks are used to execute functions at **fixed times**. These tasks
are implemented to be used similarly to cron-jobs.

Specify a list of years, months, weeks, days, hours, minutes and seconds to plan
the execution. Passing an empty list is interpreted as a wildcard meaning all
possible values.

#### Keep in mind

- A datetime task will call the given function with the given parameters.
  For each function call **a new thread is started**. Make sure that the
  function to be called is thread-safe.
- There is no limit of the maximum number of simultanious task executions. Make
  sure that the function being called is able to
  **run multiple times at the same time**. Have a look at *reccuring tasks* if
  your task / task group must only run once at a time.

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

`TODO`


### Reccuring tasks

Reccuring tasks are used to execute functions at **fixed intervals**.

It is possible to prioritize certain tasks. You can also put the tasks into
groups and prioritize those groups.

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

#### Examples

`TODO`


## Used modules

For logging I use tizianerlenbergs [logHandler.py](https://github.com/tizianerlenberg/multiSSH/blob/6f48a3a5d0542fcb61682b9cb835b769b60e406b/logHandler.py) from his [multiSSH](https://github.com/tizianerlenberg/multiSSH) repository.
