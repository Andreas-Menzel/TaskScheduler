from running_tasks_visualizer import *



from time import sleep
def backup(increment):
    # make backup
    sleep(5)
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



# running_tasks_visualizer watch-command
watch()
