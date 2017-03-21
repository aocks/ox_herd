"""Views for ox_herd flask blueprint.
"""

import datetime
import logging
import os
import glob
import collections

import markdown

from flask import render_template, redirect, request, Markup, url_for, escape
from flask.ext.login import login_required

from ox_herd.file_cache import cache_utils
from ox_herd.ui.flask_web_ui.ox_herd import OX_HERD_BP
from ox_herd.core import scheduling
from ox_herd.ui.flask_web_ui.ox_herd import forms
from ox_herd import settings

from collections import namedtuple
def d_to_nt(dictionary):
    "Convert dictionaryt to namedtuple"
    return namedtuple('GenericDict', dictionary.keys())(**dictionary)

def reprocess_master(keep_recent=16):
    result = {'tests' : []}
    root = cache_utils.get_path('test_results')
    files = list(reversed(sorted(glob.glob(os.path.join(root, '*.pkl')))))
    time_and_file = list(reversed(sorted([
        (os.path.getmtime(f), f) for f in files])))
    delete_old_data(time_and_file[keep_recent:])
    time_and_file = time_and_file[:keep_recent]
    for dummy_time, my_file in time_and_file:
        name = os.path.basename(my_file)
        my_test = TestSummary(name)
        my_test.read_from_file(root=root)
        result['tests'].append(my_test.as_row())
    result['processed_at'] = datetime.datetime.now()
    cache_utils.pickle_with_name(result, 'test_master.pickle', overwrite=True)

class TestSummary(object):

    def __init__(self, name, data=None, error=None):
        self.name = name
        self.data = data
        self.error = error

    def read_from_file(self, root=None):
        root = root if root else cache_utils.get_path('test_results')
        try:
            self.data = cache_utils.unpickle_name('test_results/' + self.name)
        except Exception as problem:
            prob_str = str(problem)
            if len(prob_str) > 95:
                prob_str = prob_str[:95] + '...'
            self.error = 'Could not understand test %s because %s' % (
                self.name[0:80], prob_str)

    def as_row(self):
        assert self.data or self.error, 'Cannot make row without info.'
        name_cell = '<TD><A HREF="%s?test_name=%s">%s</A></TD>' % (
            url_for('ox_herd.show_test'), self.name, self.name)
        if self.error:
            return Markup('<TR>%s<TD colspan="4">%s</TD></TR>' % (
                name_cell, escape(self.error)))
        else:
            return Markup('<TR>\n%s\n%s</TR>' % (
                name_cell, '\n'.join(['<TD>%s</TD>' % i for i in [
                    self.data['summary'].get('failed', 0),
                    self.data['summary'].get('passed', 0),
                    '%.2f' % self.data['summary']['duration'],
                    self.data['created_at']]])))

def delete_old_data(old_data):
    for old_time, old_file in old_data:
        logging.debug('Deleting old file %s.', old_file)
        os.remove(old_file)

@OX_HERD_BP.route('/')
@OX_HERD_BP.route('/index')
@login_required
def index():
    """Main page for ox_herd.

    Usually will not be true root since blueprint will
    be registered with url_prefix.
    """
    commands = collections.OrderedDict([
        (name, Markup('<A HREF="%s">%s</A>' % (
            url_for('ox_herd.%s' % name), name))) for name in [
                'show_test', 'list_tests', 'show_scheduled', 'cancel_job',
                'schedule_job', 'show_job', 'cleanup_job', 'requeue_job']])

    return render_template('ox_herd/templates/intro.html', commands=commands)


@OX_HERD_BP.route('/list_tests')
@login_required
def list_tests():
    "Show list of available test results."

    master_file = cache_utils.get_path('test_master.pickle')
    if 1 or not os.path.exists(master_file):#FIXME do not reproc every time!
        reprocess_master()
    if not os.path.exists(master_file):        
        raise Exception('No test master file found at %s' % master_file) #FIXME
    test_master = cache_utils.unpickle_name('test_master.pickle')
    return render_template(
        'test_list.html', title='Test List', test_data=test_master)


@OX_HERD_BP.route('/show_test')
@login_required
def show_test():
    "Show results for a test."

    test_name = request.args.get('test_name', None)
    try:
        test_data = cache_utils.unpickle_name('test_results/' + test_name)
    except Exception as problem:
        return render_template(
            'generic_error.html',title='Could not find test',
            commentary='Could not find test %s because %s' % (
                problem, test_name))

    return render_template('test_report.html', title='Test Report',
                           test_data=test_data, test_name=test_name)

@OX_HERD_BP.route('/show_scheduled')
@login_required
def show_scheduled():
    queue_names = request.args.get('queue_names', settings.QUEUE_NAMES)
    queue_names = list(sorted(queue_names.split()))
    my_tests = scheduling.SimpleScheduler.get_scheduled_tests()
    failed_jobs = scheduling.SimpleScheduler.get_failed_jobs()
    queued = scheduling.SimpleScheduler.get_queued_jobs(queue_names)
    return render_template('test_schedule.html', test_schedule=my_tests,
                           queue_names=queue_names, failed_jobs=failed_jobs,
                           queued=queued)

@OX_HERD_BP.route('/show_job')
@login_required
def show_job():
    jid = request.args.get('jid', None)
    if not jid:
        return redirect(url_for('ox_herd.show_scheduled'))
    else:
        job_info = scheduling.SimpleScheduler.find_job(jid)
        if hasattr(job_info, 'kwargs'):
            job_info = job_info.kwargs['ox_test_args']
        if not hasattr(job_info, 'jid'):
            job_info.jid = jid
        return render_template('job_info.html', item=job_info)

@OX_HERD_BP.route('/launch_job')
@login_required
def launch_job():
    jid = request.args.get('jid', None)
    if jid:
        new_job = scheduling.SimpleScheduler.launch_job(jid)
        new_jid = new_job.id
    else:
        new_jid = None
    
    return render_template('launch_job.html', jid=new_jid)

@OX_HERD_BP.route('/cancel_job')
@login_required
def cancel_job():
    jid = request.args.get('jid', None)
    if not jid:
        return render_template('cancel_job.html')
    else:
        cancel = scheduling.SimpleScheduler.cancel_job(jid)
        return render_template('cancel_job.html', jid=jid, cancel=cancel)

@OX_HERD_BP.route('/cleanup_job')
@login_required
def cleanup_job():
    cleanup = None
    jid = request.args.get('jid', None)
    if jid:
        cleanup = scheduling.SimpleScheduler.cleanup_job(jid)
    return render_template('cleanup_job.html', jid=jid, cleanup=cleanup)


@OX_HERD_BP.route('/requeue_job')
@login_required
def requeue_job():
    jid = request.args.get('jid', None)
    if jid:
        requeue = scheduling.SimpleScheduler.requeue_job(jid)
    return render_template('requeue_job.html', jid=jid, requeue=requeue)


@OX_HERD_BP.route('/schedule_job', methods=['GET', 'POST'])
@login_required
def schedule_job():

    jid = request.args.get('jid', None)
    if jid and request.method == 'GET':
        my_args = scheduling.SimpleScheduler.jobid_to_argrec(jid)
        my_form = forms.SchedJobForm(obj=my_args)
        my_form.name.data += '_copy'
    else:
        my_form = forms.SchedJobForm()

    if my_form.validate_on_submit():
        info = forms.GenericRecord()
        my_form.populate_obj(info)
        job = scheduling.SimpleScheduler.add_to_schedule(info)
        return redirect('%s?jid=%s' % (
            url_for('ox_herd.show_job'), job.id))
        
    return render_template(
        'ox_wtf.html', form=my_form, title='Schedule Test',
        intro=Markup(markdown.markdown(my_form.__doc__, extensions=[
            'fenced_code', 'tables'])))
    
