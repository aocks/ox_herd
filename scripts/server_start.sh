#!/bin/sh

# This is a script used to start everything up on docker.

# Restart redis server just to make sure it is up and working.
/etc/init.d/redis-server restart

su - -c "rq worker" ox_user 2>&1 | \
   rotatelogs /home/ox_user/ox_server/logs/rq_worker.log 86400 10M &
su - -c rqscheduler ox_user 2>&1 | \
   rotatelogs /home/ox_user/ox_server/logs/rqscheduler.log 86400 10M&

export PYTHONPATH=/home/ox_user/ox_server/ox_herd
echo "git log is: `cd /home/ox_user/ox_server/ox_herd && git log | head -7`"
echo "PYTHONPATH is $PYTHONPATH"
su - -c "python3 /home/ox_user/ox_server/ox_herd/ox_herd/scripts/serve_ox_herd.py" ox_user 2>&1 | \
   rotatelogs -e -f /home/ox_user/ox_server/logs/serve_ox_herd.log 86400 10M
