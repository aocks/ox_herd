"""Tools to check and verify health.

"""

import doctest
import time
import logging
import datetime
import threading

import typing

from redis import Redis
from rq import Queue, Worker
from rq_scheduler import Scheduler


class RQDoc:
    """Doctor to check on health of python rq services.

This class is meant to be able to check on python rq services.
The idea is that you can call the check method which does
some things to verify liveness. See docs on that as well
as _regr_test method for details.
    """

    default_complain = ValueError

    def __init__(self, complain=None, q_mode: str = 's'):
        """Initializer.

        :param complain=None:  Optional callable which takes a single
                               string argument descricing problem we had
                               in probing a queue and complains. See
                               ProbeQueue class for details. This is used
                               as default when we call self.launch_probe.

                               If you provide None, then we use the value
                               of the class variable default_complain. This
                               lets you change the default_complain to affect
                               global default behaviour.

        :param q_mode='s':     How to enqueue the job when checking queues:
                                 - 's':  Use scheduler to enqueue so that
                                         both queue and scheduler are checked.
                                 - 'q':  Use queue directly so scheduler
                                         not checked.

        """
        self.complain = (
            complain if complain else self.__class__.default_complain)
        self.q_mode = q_mode

    def check(self, probe_time: int,
              check_queues: typing.Union[str, typing.Sequence[str]],
              complain: callable = None) -> str:
        """Check liveness.

        :param probe_time:  Integer indicating how long to wait (in seconds)
                            for probing the queue. A value of 0 indicates
                            no probe.

        :param check_queues:  Either a string of the form 'q1/q2' or a sequence
                              of the form ['q1', 'q2'] naming the queues to
                              check for liveness.

        :param complain=None:  Passed to self.launch_probe.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  'OK' if things look OK.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Calls self.check_workers and self.launch_probe to verify
                  liveness of desired queues. The idea is that this is a
                  high-level method that you can call to do all known checks.

        """
        sdict = {}
        self.check_workers(check_queues)
        if probe_time.strip():
            probe_time = int(probe_time)
            if probe_time < 0:
                raise ValueError('Cannot have negative probe_time')
            for qname in self.queue_name_list(check_queues):
                self.launch_probe(probe_time, qname, sdict, complain)
        return 'OK'

    @staticmethod
    def queue_name_list(str_or_seq: typing.Union[str, typing.Sequence[str]]):
        """

        :param str_or_seq:    Either a string of the form 'q1/q2' or a sequence
                              of the form ['q1', 'q2'] naming the queues to
                              check for liveness.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  List of strings indicating queues to check.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Translate str or sequence into list of strings suitable
                  for other methods.
        """
        if isinstance(str_or_seq, str):
            return str_or_seq.split('/')
        return str_or_seq

    def check_workers(
            self, check_queues: typing.Union[str, typing.Sequence[str]]):
        """Check that workers are alive.

        :param check_queues:  List or sequence of strings indicating queues
                              to check. See queue_name_list for format if
                              you want to pass a string instead of list.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  The string 'OK' if workers are alive or raises ValueError
                  if something is wrong.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Go through queues in check_queues and see if there is
                  a worker in python rq to work on that queue.

        """
        queue_counts = {}
        worker_list = Worker.all(connection=Redis())
        for worker in worker_list:
            for qname in worker.queue_names():
                queue_counts[qname] = 1 + queue_counts.get(qname, 0)
        for qname in self.queue_name_list(check_queues):
            if not queue_counts.get(qname, None):
                raise ValueError('No workers found for queue "%s"' % qname)
        return 'OK'

    def launch_probe(self, probe_time: int, qname: str, sdict: dict,
                     complain: callable = None):
        """Launch a probe into the given queue to verify things work.

        :param probe_time: Integer probe time > 0.

        :param qname:  String name of queue to check.

        :param sdict:  Dictionary which will have sdict['status'] set to
                       either 'good' or 'bad' depending on outcome of
                       probe.

        :param complain=None:  Optional callable which takes a single
                               string argument descricing problem we had
                               in probing a queue and complains. If this
                               is None, we use self.complain.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Create an instance of ProbeQueue and start it in
                  a separate thread to verify that we can launch jobs
                  into the queue and have them run. See ProbeQueue for
                  more details.

        """
        probe = ProbeQueue(probe_time, qname, sdict,
                           complain if complain else self.complain,
                           q_mode=self.q_mode)
        probe.daemon = True
        probe.start()

    @staticmethod
    def _regr_test():
        """Illustrate how checking things works.

First setup basic boiler-plate imports

>>> import random, time
>>> from redis import Redis
>>> from rq import SimpleWorker, Queue
>>> from ox_herd.core import health

Next setup the RQDoc to check health along with queues and workers.

>>> doc = health.RQDoc(q_mode='q')  # just check mode 'q' for simplicity
>>> qname = 'test_q_%i' % random.randint(0, 100000)
>>> queue = Queue(connection=Redis(), name=qname)
>>> worker = SimpleWorker([queue], connection=queue.connection)

Note that we have not started worker yet so calling check method
will return an exception for our named queue since it has no
running workers.

>>> try:  # verify that we get exception if worker not running
...     doc.check(1, qname)
... except ValueError as problem:
...     print('got problem: %s' % str(problem)) # doctest: +ELLIPSIS
...
got problem: No workers found for queue "test_q_..."

Now we create and queue the doc.check_workers function into the queue.
This is basically just a hack so that when we run the worker in burst
mode the job will get run while the worker is active. We could also
do a potentially cleaner version of this test using threading or
subprocess to have the worker running in the background while we
check that it is alive, but this is a simpler test.

>>> job = queue.enqueue(doc.check_workers, qname)
>>> sdict = {}
>>> probe = doc.launch_probe(1, qname, sdict)
>>> worker.work(burst=True) # verify that doing check with running worker
True
>>> job.result              # is fine with no exception
'OK'
>>> job.get_status()
'finished'
>>> time.sleep(3)
>>> sdict
{'status': 'good'}

Now we are going to verify that the probe will detect a stuck queue.
We enqueue a job that just sleeps to block the queue and then we launch
a quick probe and verify that things look bad.

>>> sjob = queue.enqueue(time.sleep, 3)
>>> sdict = {}
>>> probe = doc.launch_probe(1, qname, sdict)
>>> worker.work(burst=True) # verify that doing check with running worker
True
>>> time.sleep(5)
>>> sdict
{'status': 'bad'}

        """


def return_true():
    """Return True

Simple function used to check liveness of workers.
    """
    return True


class ProbeQueue(threading.Thread):
    """Sub-class of Thread to probe a queue to see if it is working.

The idea is that you create an instance of this class with args
described in __init__ and then start the thread to check if there is
a live working queue.

This needs to be a thread since if you are using this in a web server,
then you may want your server to return a response and do the probe
in the background as a separate thread which reports complaints
via the `complain` argument passed to __init__.
    """

    def __init__(self, probe_time: int, qname: str, sdict: dict,
                 complain: callable, q_mode: str, *args, **kwargs):
        """Initializer.

        :param probe_time: Integer probe time > 0.

        :param qname:  String name of queue to check.

        :param sdict:  Dictionary which will have sdict['status'] set to
                       either 'good' or 'bad' depending on outcome of
                       probe.

        :param complain=None:  callable which takes a single
                               string argument descricing problem we had
                               in probing a queue and complains. If this
                               returns an instance of Exception, then we
                               raise that.

                               This method is helpful since this is
                               a thread and so raising an exception may
                               not be seen by main thread. Hence you can
                               provide a custom complainer.

        :param q_mode='s':     How to enqueue the job when checking queues:
                                 - 's':  Use scheduler to enqueue so that
                                         both queue and scheduler are checked.
                                 - 'q':  Use queue directly so scheduler
                                         not checked.

        :param *args, **kwargs:   Passed to Thread.__init__.
        """
        self.probe_time = probe_time
        self.qname = qname
        self.sdict = sdict
        self.complain = complain
        self.q_mode = q_mode
        super().__init__(*args, **kwargs)

    def queue_job(self):
        """Enqueue a job based on self.q_mode and return queued job.

This will enqueue directly if q_mode == 'q' and use a scheduler if
the q_mode == 's'>
        """
        args = [return_true]
        kwargs = {'ttl': 10*self.probe_time,
                  'result_ttl': 20*self.probe_time}
        if self.q_mode == 'q':
            my_queue = Queue(self.qname, connection=Redis())
            launcher = my_queue.enqueue
        elif self.q_mode == 's':
            sched = Scheduler(queue_name=self.qname, connection=Redis())
            launcher = sched.cron
            kwargs = {'kwargs': kwargs, 'cron_string' = '* * * * *',
                      func=args.pop}
        else:
            raise ValueError('Invalid q_mode: "%s"' % self.q_mode)
        job = launcher(*args, **kwargs)
        return job

    def run(self):
        """Run the thread.
        """
        start = datetime.datetime.utcnow()
        job = self.queue_job()
        for keep_trying in [1, 1, 1, 1, 1, 0]:  # try 5 times
            logging.info('Sleeping to wait for %s', job)
            time.sleep(self.probe_time + 1)
            now = datetime.datetime.utcnow()
            if (now - start).total_seconds() > self.probe_time:
                break
            if not keep_trying:
                self.issue_complaint(
                    'Could not sleep for %s' % self.probe_time)
        assert (now - start).total_seconds() > self.probe_time
        status = job.get_status()
        if status != 'finished':
            msg = 'At UTC=%s, job %s launched at %s has status %s' % (
                datetime.datetime.utcnow(), job, start, status)
            msg += ('\n*IMPORTANT*:  this could indicate that either the\n'
                    'rq worker or rqscheduler process is *DOWN*')
            self.sdict['status'] = 'bad'
            self.issue_complaint(msg)
        self.sdict['status'] = 'good'
        logging.info('Job %s completed with status %s', job, status)

    def issue_complaint(self, msg: str):
        """Issue a complaint.

        :param msg:    String message we complain about.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  The result of calling self.complain(msg).

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Call self.complain on given msg to generate a complaint
                  about something wrong with a queue. If the compalint is
                  a sub-class of Exception, we raise it.
        """
        complaint = self.complain(msg)
        if isinstance(complaint, Exception):
            raise complaint
        return complaint


if __name__ == '__main__':
    doctest.testmod()
    print('Finished Tests')
