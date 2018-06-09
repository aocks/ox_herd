"""Views for ox_herd flask blueprint.
"""

import copy
import logging
import os
import collections

import markdown

from flask import render_template, redirect, request, Markup, url_for
from flask_login import login_required

from ox_herd.ui.flask_web_ui.ox_herd import OX_HERD_BP
from ox_herd.core import scheduling, simple_ox_tasks, ox_run_db
from ox_herd import settings
from ox_herd.core.plugins import manager as plugin_manager

from collections import namedtuple
def d_to_nt(dictionary):
    "Convert dictionaryt to namedtuple"
    return namedtuple('GenericDict', dictionary.keys())(**dictionary)

def delete_old_data(old_data):
    for old_time, old_file in old_data:
        logging.debug('Deleting old file %s.', old_file)
        os.remove(old_file)

@OX_HERD_BP.route('/')
@OX_HERD_BP.route('/index')
@OX_HERD_BP.route('/show_index')
@login_required
def index():
    """Main page for ox_herd.

    Usually will not be true root since blueprint will
    be registered with url_prefix.
    """
    commands = collections.OrderedDict([
        (name, Markup('<A HREF="%s">%s</A>' % (
            url_for('ox_herd.%s' % name), name))) for name in [
                'show_plugins', 'list_tasks', 'show_scheduled', 'show_task_log',
                'cancel_job', 'cleanup_job']])

    return render_template('ox_herd/templates/intro.html', commands=commands)


@OX_HERD_BP.route('/list_tasks')
@login_required
def list_tasks():
    "Show list of tasks so you can inspect them."

    tasks = ox_run_db.create().get_tasks()
    return render_template('task_list.html', title='Task List', tasks=tasks)


@OX_HERD_BP.route('/show_task_log')
@login_required
def show_task_log():
    "Show log of tasks run."
    
    run_db = ox_run_db.create()
    start_utc=request.args.get('start_utc', None)
    end_utc=request.args.get('end_utc', None)
    tasks = run_db.get_tasks(start_utc=start_utc, end_utc=end_utc)
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
        end_utc=end_utc, task_dict=task_dict)


@OX_HERD_BP.route('/show_task')
@login_required
def show_task():
    "Show information about a task."

    task_id = request.args.get('task_id', None)
    run_db = ox_run_db.create()
    try:
        task_data = run_db.get_task(task_id)
        if not task_data:
            raise KeyError('No task with id %s' % str(task_id))
    except Exception as problem:
        return render_template(
            'generic_error.html',title='Could not find task',
            commentary='Could not find task with id %s because %s' % (
                task_id, problem))

    template = request.args.get('template', task_data.template)
    template = template if (
        template and template.strip() and template != 'default') else (
            'generic_ox_task_result.html')
    return render_template(template, title='Task Report', task_data=task_data)

@OX_HERD_BP.route('/show_scheduled')
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

@OX_HERD_BP.route('/show_job')
@login_required
def show_job():
    jid = request.args.get('jid', None)
    if not jid:
        return redirect(url_for('ox_herd.index'))
    else:
        my_job = scheduling.OxScheduler.find_job(jid)
        ox_herd_task = getattr(my_job, 'kwargs', {}).get('ox_herd_task', None)
        if ox_herd_task is None:
            raise ValueError('Job for id %s has no ox_herd_task (job is %s)' % (
                jid, str(my_job))) # FIXME: should show nice error not raise
        return render_template('job_info.html', item=my_job)


@OX_HERD_BP.route('/launch_job')
@login_required
def launch_job():
    jid = request.args.get('jid', None)
    if jid:
        new_job = scheduling.OxScheduler.launch_job(jid)
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
        cancel = scheduling.OxScheduler.cancel_job(jid)
        return render_template('cancel_job.html', jid=jid, cancel=cancel)

@OX_HERD_BP.route('/cleanup_job')
@login_required
def cleanup_job():
    cleanup = None
    jid = request.args.get('jid', None)
    if jid:
        cleanup = scheduling.OxScheduler.cleanup_job(jid)
    return render_template('cleanup_job.html', jid=jid, cleanup=cleanup)


@OX_HERD_BP.route('/requeue_job')
@login_required
def requeue_job():
    jid = request.args.get('jid', None)
    if jid:
        requeue = scheduling.OxScheduler.requeue_job(jid)
    return render_template('requeue_job.html', jid=jid, requeue=requeue)



@OX_HERD_BP.route('/show_plugins')
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


@OX_HERD_BP.route('/use_plugin', methods=['GET', 'POST'])
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
    my_form_cls = my_comp.get_flask_form()
    my_form = my_form_cls()
    if my_form.validate_on_submit():
        klass = my_comp.get_ox_task_cls()
        info = klass(name=my_form.name.data)
        my_form.populate_obj(info)
        job = scheduling.OxScheduler.add_to_schedule(info, info.manager)
        return redirect('%s?jid=%s' % (url_for('ox_herd.show_job'), job.id))
    else:
        template = my_comp.get_flask_form_template()
        intro=Markup(markdown.markdown(my_form.__doc__, extensions=[
            'fenced_code', 'tables']))
        return render_template(
            template, form=my_form, intro=intro, title=(
                'Form for component %s of plugin %s' % (plugcomp, plugname)))
            

@OX_HERD_BP.route('/schedule_job', methods=['GET', 'POST'])
@login_required
def schedule_job():

    jid = request.args.get('jid', None)
    my_job = scheduling.OxScheduler.find_job(jid)
    my_args = my_job.kwargs.get('ox_herd_task', None)
    if my_args is None:
        raise ValueError("job %s had no kwargs['ox_herd_task']"%str(my_job))
    my_args = copy.deepcopy(my_args)
    my_form_cls = my_args.get_flask_form()
    my_form = my_form_cls(obj=my_args)

    if my_form.validate_on_submit():
        my_form.populate_obj(my_args)
        job = scheduling.OxScheduler.add_to_schedule(my_args, getattr(
            my_args, 'manager', 'rq'))
        return redirect('%s?jid=%s' % (url_for('ox_herd.show_job'), job.id))

    my_form.name.data += '_copy' # change name to add _copy if making new job

    return render_template(
        'ox_wtf.html', form=my_form, title='Schedule Test',
        intro=Markup(markdown.markdown(my_form.__doc__, extensions=[
            'fenced_code', 'tables'])))


@OX_HERD_BP.route('/delete_task_from_db')
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
