#!/bin/sh

# This is a script used to start everything up on docker.

su - -c "rq worker" ox_user 2>&1 | \
   rotatelogs /home/ox_user/ox_server/logs/rq_worker.log 86400 &
su - -c rqscheduler ox_user 2>&1 | \
   rotatelogs /home/ox_user/ox_server/logs/rqscheduler.log 86400 &

export PYTHONPATH=/home/ox_user/ox_server/ox_herd
echo "output of git log is: `git log | head -7`"
echo "PYTHONPATH is $PYTHONPATH"
python3 /home/ox_user/ox_server/ox_herd/ox_herd/scripts/serve_ox_herd.py

