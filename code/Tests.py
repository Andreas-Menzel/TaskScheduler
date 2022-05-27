from TaskScheduler import *

# DEBUG: Test function. Can be removed after testing.
def test_function(task_id = None):
    #print(f'+ Started task {task_id}.')
    time.sleep(2)
    #print(f'- Stopped task {task_id}.')


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
