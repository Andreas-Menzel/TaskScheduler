import sys
sys.path.append('../..')
import TaskScheduler

from datetime import timedelta
from time import sleep


# {
#     'datetime': {
#         <group_id_1>: {
#             'max_executions': <number_of_allowed_simultaneous_executions>,
#             'tasks': <task_id_1>, <task_id_2>, ...
#         }, ...
#     }, 'reccuring': {
#         <group_id_1>: {
#             'max_executions': <number_of_allowed_simultaneous_executions>,
#             'tasks': <task_id_1>, <task_id_2>, ...
#         }, ...
#     }
# }
# NOTE: Create a separate group for each task
groups = { 'datetime': {}, 'reccuring': {} }
# {
#     'datetime': {
#         <task_id_1>: <number_of_current_executions>, ...
#     }, 'reccuring': {
#         <task_id_1>: <number_of_current_executions>, ...
#     }
# }
running_tasks = { 'datetime': {}, 'reccuring': {} }

def reccuring_function(task_id, function, arguments):
    global running_tasks

    running_tasks['reccuring'][task_id] += 1
    function(*arguments)
    running_tasks['reccuring'][task_id] -= 1


def reccuring_schedule(task_id, _groups, function, arguments, timedelta, use_exec_log = False, max_instances = 1, priority = (0, 0)):
    global running_tasks
    global groups
    running_tasks['reccuring'][task_id] = 0
    set_reccuring_group(task_id, max_instances, 0)
    groups['reccuring'][task_id]['tasks'].append(task_id)
    for group in _groups:
        set_reccuring_group(group, -1, 0)
        groups['reccuring'][group]['tasks'].append(task_id)
    TaskScheduler.reccuring_schedule(task_id, _groups, reccuring_function, [task_id, function, arguments], timedelta, use_exec_log, max_instances, priority)

def set_reccuring_group(group_id, max_tasks, priority = 0):
    global groups
    if not group_id in groups['reccuring']:
        groups['reccuring'][group_id] = { 'max_executions': max_tasks, 'tasks': [] }
        TaskScheduler.set_reccuring_group(group_id, max_tasks, priority)



def watch():
    column_size = len(max(groups['reccuring'], key=len))
    if column_size < 7:
        column_size = 7

    for group in groups['reccuring']:
        print(f'| {group.center(column_size)} ', end='')
    print('|')
    for group in groups['reccuring']:
        print(f'+-{"-"*(column_size)}-', end='')
    print('+')

    while True:
        for group_id, group in groups['reccuring'].items():
            current_executions = 0
            for task in group['tasks']:
                if task in running_tasks['reccuring']:
                    current_executions += running_tasks['reccuring'][task]
            output = f'{current_executions} / {group["max_executions"]}'
            output = output.replace('-1', '∞')
            print('| ' + output.center(column_size) + ' ', end='')
        print('|')
        sleep(1)
