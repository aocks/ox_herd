"""Views for ox_herd flask blueprint.
"""

import datetime
import copy
import logging
import os
import collections
from collections import namedtuple
import json

import markdown

from flask import (render_template, redirect, request, Markup, url_for, abort)
from flask_login import login_required, current_user

from ox_herd.ui.flask_web_ui.ox_herd import core
from ox_herd.core import health
from ox_herd.core import scheduling, ox_run_db
from ox_herd import settings
from ox_herd.core.plugins import (
    manager as plugin_manager, base as ox_herd_base)


def d_to_nt(dictionary):
    "Convert dictionaryt to namedtuple"
    return namedtuple('GenericDict', dictionary.keys())(**dictionary)


def delete_old_data(old_data):
    for old_time, old_file in old_data:
        logging.debug('Deleting old file %s.', old_file)
        os.remove(old_file)


@core.ox_herd_route('/')
@login_required
def home():
    'redirect to index'
    return index()


@core.ox_herd_route('/show_index')
@login_required
def show_index():
    'redirect to index'
    return index()


@core.ox_herd_route('/index')
@login_required
def index():
    """Main page for ox_herd.

    Usually will not be true root since blueprint will
    be registered with url_prefix.
    """
    commands = collections.OrderedDict([
        (name, Markup('<A HREF="%s">%s</A>' % (
            url_for('ox_herd.%s' % name), name))) for name in [
                'show_plugins', 'list_tasks', 'show_scheduled',
                'show_task_log', 'cancel_job', 'cleanup_job']])

    return render_template('ox_herd/templates/intro.html', commands=commands)


@core.ox_herd_route('/list_tasks')
@login_required
def list_tasks():
    "Show list of tasks so you can inspect them."

    my_db = ox_run_db.create()
    limit = int(request.args.get('limit', 100))
    start_utc = request.args.get('start_utc', None)
    end_utc = request.args.get('end_utc', None)
    tasks = my_db.get_tasks(start_utc=start_utc, end_utc=end_utc)
    total = len(tasks)
    tasks = my_db.limit_task_count(tasks, limit)
    return render_template('task_list.html', title='Task List',
                           tasks=tasks, total=total, limit=limit)


@core.ox_herd_route('/show_task_log')
@login_required
def show_task_log():
    "Show log of tasks run."

    run_db = ox_run_db.create()
    start_utc = request.args.get('start_utc', None)
    end_utc = request.args.get('end_utc', None)
    limit = int(request.args.get('limit', 100))
    tasks = run_db.get_tasks(start_utc=start_utc, end_utc=end_utc)
    tasks = run_db.limit_task_count(tasks, limit)
    other = []
    task_dict = collections.OrderedDict([('started', []), ('finished', [])])
    for item in reversed(sorted(
            tasks, key=lambda t: (t.task_end_utc, t.task_start_utc))):
        if item.task_status in task_dict:
            task_dict[item.task_status].append(item)
        else:
            other.append(item)
    task_dict['other'] = other

    return render_template(
        'task_log.html', title='Task log', start_utc=start_utc,
        end_utc=end_utc, task_dict=task_dict, limit=limit)


@core.ox_herd_route('/show_task')
@login_required
def show_task():
    "Show information about a task."

    task_id = request.args.get('task_id', None)
    run_db = ox_run_db.create()
    try:
        task_data = run_db.get_task(task_id)
        if not task_data:
            raise KeyError('No task with id %s' % str(task_id))
    except Exception as problem:  # pylint: disable=broad-except
        return render_template(
            'generic_error.html', title='Could not find task',
            commentary='Could not find task with id %s because %s' % (
                task_id, problem))

    template = request.args.get('template', task_data.template)
    template = template if (
        template and template.strip() and template != 'default') else (
            'generic_ox_task_result.html')
    return render_template(template, title='Task Report', task_data=task_data)


@core.ox_herd_route('/show_scheduled')
@login_required
def show_scheduled():
    queue_names = request.args.get('queue_names', settings.QUEUE_NAMES)
    queue_names = list(sorted(queue_names.split()))
    my_jobs = scheduling.OxScheduler.get_scheduled_jobs()
    failed_jobs = scheduling.OxScheduler.get_failed_jobs()
    queued = scheduling.OxScheduler.get_queued_jobs(queue_names)
    return render_template('task_schedule.html', task_schedule=my_jobs,
                           queue_names=queue_names, failed_jobs=failed_jobs,
                           queued=queued)


@core.ox_herd_route('/show_job')
@login_required
def show_job():
    jid = request.args.get('jid', None)
    if not jid:
        return redirect(url_for('ox_herd.index'))
    else:
        my_job = scheduling.OxScheduler.find_job(jid)
        ox_herd_task = getattr(my_job, 'kwargs', {}).get('ox_herd_task', None)
        if ox_herd_task is None:
            raise ValueError(
                'Job for id %s has no ox_herd_task (job is %s)' % (
                    jid,
                    str(my_job)))  # FIXME: should show nice error not raise
        return render_template('job_info.html', item=my_job)


@core.ox_herd_route('/launch_job')
@login_required
def launch_job():
    jid = request.args.get('jid', None)
    if jid:
        new_job = scheduling.OxScheduler.launch_job(jid)
        new_jid = new_job.id
    else:
        new_jid = None

    return render_template('launch_job.html', jid=new_jid)


@core.ox_herd_route('/cancel_job')
@login_required
def cancel_job():
    jid = request.args.get('jid', None)
    if not jid:
        return render_template('cancel_job.html')

    cancel = scheduling.OxScheduler.cancel_job(jid)
    return render_template('cancel_job.html', jid=jid, cancel=cancel)


@core.ox_herd_route('/cleanup_job')
@login_required
def cleanup_job():
    cleanup = None
    jid = request.args.get('jid', None)
    if jid:
        cleanup = scheduling.OxScheduler.cleanup_job(jid)
    return render_template('cleanup_job.html', jid=jid, cleanup=cleanup)


@core.ox_herd_route('/requeue_job')
@login_required
def requeue_job():
    jid = request.args.get('jid', None)
    if jid:
        requeue = scheduling.OxScheduler.requeue_job(jid)
    return render_template('requeue_job.html', jid=jid, requeue=requeue)


@core.ox_herd_route('/show_plugins')
@login_required
def show_plugins():
    actives = plugin_manager.PluginManager.get_active_plugins()
    components = []
    for name, plug in actives.items():
        comp_list = plug.get_components()
        logging.debug('Processing plugin %s.', name)
        urls = [(c.cmd_name(), '%s?plugname=%s&plugcomp=%s' % (
            url_for('ox_herd.use_plugin'), name, c.cmd_name()))
                for c in comp_list]
        components.append((name, urls))
    return render_template('show_plugins.html', components=components)


@core.ox_herd_route('/use_plugin', methods=['GET', 'POST'])
@login_required
def use_plugin():
    plugname = request.args.get('plugname', '').strip()
    plugcomp = request.args.get('plugcomp', '').strip()
    plugdict = plugin_manager.PluginManager.get_active_plugins()
    if plugname not in plugdict:
        return 'FIXME: plugin named %s not found in %s' % (plugname, list(
            plugdict))
    myplug = plugdict[plugname]
    compdict = dict([(c.cmd_name(), c) for c in myplug.get_components()])
    if plugcomp not in compdict:
        return 'FIXME: component named %s not found' % plugcomp
    my_comp = compdict[plugcomp]
    my_form_cls = my_comp.get_flask_form_via_cls()
    my_form = my_form_cls()
    if my_form.validate_on_submit():
        klass = my_comp.get_ox_task_cls()
        info = klass(name=my_form.name.data)
        my_form.populate_obj(info)
        job = scheduling.OxScheduler.add_to_schedule(info, info.manager)
        return redirect('%s?jid=%s' % (url_for('ox_herd.show_job'), job.id))

    template = my_comp.get_flask_form_template()
    intro = Markup(markdown.markdown(my_form.__doc__, extensions=[
        'fenced_code', 'tables']))
    return render_template(
        template, form=my_form, intro=intro, title=(
            'Form for component %s of plugin %s' % (plugcomp, plugname)))


@core.ox_herd_route('/schedule_job', methods=['GET', 'POST'])
@login_required
def schedule_job():
    """Schedule a job and configure its parameters.
    """
    jid = request.args.get('jid', None)
    my_job = scheduling.OxScheduler.find_job(jid)
    my_args = my_job.kwargs.get('ox_herd_task', None)
    if my_args is None:
        raise ValueError("job %s had no kwargs['ox_herd_task']" % str(my_job))
    my_args = copy.deepcopy(my_args)
    my_form = core.make_form_for_task(my_args)

    if my_form.validate_on_submit():
        my_form.populate_obj(my_args)
        job = scheduling.OxScheduler.add_to_schedule(my_args, getattr(
            my_args, 'manager', 'rq'))
        return redirect('%s?jid=%s' % (url_for('ox_herd.show_job'), job.id))

    my_form.name.data += '_copy'  # change name to add _copy if making new job

    return render_template(
        'ox_wtf.html', form=my_form, title='Schedule Test',
        intro=Markup(markdown.markdown(my_form.__doc__, extensions=[
            'fenced_code', 'tables'])))


@core.ox_herd_route('/delete_task_from_db')
@login_required
def delete_task_from_db():
    """Delete a task from the task database.

    This is mainly intended to be used from the task list and not so
    useful directly since it requires the task_id.
    """
    task_id = request.args.get('task_id', None)
    if task_id:
        run_db = ox_run_db.create()
        run_db.delete_task(task_id)
        return render_template('generic_display.html', commentary=(
            'Delete task with id %s from database.' % task_id))
    return render_template('generic_display.html', commentary=(
        'Found no task_id so cannot do anything.'))


@core.ox_herd_route('/health_check', noauth=True)
def health_check():
    """Check if system and rq worker and scheduler are healthy.

You can set the value of OX_RQ_DOC.complain at runtime to be a function
which takes a string describing problems with th worker queues and reports
them (e.g., by doing sentry.capture or your own custom stuff).
    """
    try:  # Use try block so return 500 if see an exception
        token = request.args.get('token', '')
        if token not in settings.HEALTH_CHECK_TOKENS:
            logging.warning('Invalid token "%s" for health check; abort',
                            token)
            abort(403)
        logging.info('Valid token for "%s" for health_check received',
                     settings.HEALTH_CHECK_TOKENS[token])
        probe_time = request.args.get('probe_time', '900').strip()
        check_queues = request.args.get('check_queues', 'default').strip()
        doc = health.RQDoc()
        result = doc.check(probe_time, check_queues)
        return result
    except Exception as problem:  # pylint: disable=broad-except
        logging.error('Problem in health_check: %s', str(problem))
        abort(500)


@core.ox_herd_route('/get_latest/<task_name>')
@login_required
def get_latest(task_name):
    """Get info on latest finished version of task named <task_name>

If successful, you can do something like the folllowing to get
the completion time of the latest task:

   datetime.datetime.strptime(my_request.json()['task_end_utc'],
      '%Y-%m-%d %H:%M:%S.%f')

    """
    task_result = ox_run_db.create().get_latest(task_name)
    if task_result is None:
        result = {}
    else:
        result = {n: getattr(task_result, n, None) for n in [
            'task_id', 'task_name', 'task_start_utc', 'task_end_utc',
            'return_value', 'json_data', 'pickle_data']}
    return json.dumps(result), 200, {'ContentType': 'application/json'}


def _check_health_token():
    token = request.args.get('token', '')
    if token not in settings.HEALTH_CHECK_TOKENS:
        logging.warning('Invalid token "%s" for health check; abort',
                        token)
        return False
    logging.info('Valid token for "%s" for health_check received',
                 settings.HEALTH_CHECK_TOKENS[token])
    return True


@core.ox_herd_route('/record_finished_job', methods=['POST'], noauth=True)
def record_finished_job():
    """REST API endpoint to record that a job finished.

You can send a request with the following:

  - task_id:
    - The id returned by record_started_job if you have called that.
      If you have not called record_started_job and want to record
      both start and finish in one go then omit this and provide
      task_name instead (see below).
  - task_name:
    - If you have not already called record_started_job and just
      want to record the start and finish of the job, then provide
      a string name in task_name and omit task_id.
  - return_value:
    - Return value of running the task.
    """
    if current_user is None and not _check_health_token():
        abort(403)
    my_db = ox_run_db.create()
    try:
        record = json.loads(request.data)
        task_id = record.get('task_id', None)
        if task_id is None:
            task_id = my_db.record_task_start(record['task_name'])
            record.pop('task_name')
            record['task_id'] = task_id
        my_db.record_task_finish(**record)
    except KeyError as problem:
        return json.dumps({
            'result': 'error',
            'error': 'Could not find required value for "%s"' % str(
                problem)}), 400, {'ContentType': 'application/json'}
    return json.dumps({'result': 'success'}), 200, {
        'ContentType': 'application/json'}


@core.ox_herd_route('/check_jobs', noauth=True)
def check_jobs():
    """Check if various jobs have been running.

    """
    my_db = ox_run_db.create()
    late_jobs = []
    try:  # Use try block so return 500 if see an exception
        if not _check_health_token():
            abort(403)
        seconds = int(request.args.get('seconds', '3600'))
        name_list = request.args.get('names').split(',')
        my_now = datetime.datetime.utcnow()
        for name in name_list:
            logging.info('Checking task "%s"', name)
            latest = my_db.get_latest(name)
            if not latest:
                late_jobs.append((name, 'not found', 'N/A'))
            else:
                task_end_utc = datetime.datetime.strptime(
                    str(latest.task_end_utc), '%Y-%m-%d %H:%M:%S.%f')
                gap = (my_now - task_end_utc).total_seconds()
                if gap > seconds:
                    late_jobs.append((name, task_end_utc, gap))
        if late_jobs:
            msg = '\n'.join(['Found late jobs:'] + [
                '%s: finished at %s which is %s > %s seconds late' % (
                    name, task_end_utc, gap, seconds)
                for (name, task_end_utc, gap) in late_jobs])
            logging.error(msg)
            return json.dumps({'result': 'error', 'error': msg}), 412, {
                'ContentType': 'application/json'}
    except Exception as problem:  # pylint: disable=broad-except
        logging.error('Problem in health_check: %s', str(problem))
        abort(500)
    return json.dumps({'result': 'success'}), 200, {
        'ContentType': 'application/json'}


def message():
    "Show message that imported views."

    logging.info('Imported ox_herd views for flask.')
