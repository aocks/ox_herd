"""Views for ox_herd flask blueprint.
"""

import datetime
import logging
import os
import glob
import collections

from flask import render_template, redirect, request, Markup, url_for, escape
from flask.ext.login import login_required

from ox_herd.file_cache import cache_utils
from ox_herd.ui.flask_web_ui.ox_herd import OX_HERD_BP
from ox_herd.core import scheduling


@OX_HERD_BP.route('/')
def ox_herd():
    """Main page for ox_herd.

    Usually will not be true root since blueprint will
    be registered with url_prefix.
    """
    commands = collections.OrderedDict([
        (name, Markup('<A HREF="%s">%s</A>' % (
            url_for('ox_herd.%s' % name), name))) for name in [
                'show_test', 'list_tests']])

    return render_template('ox_herd/templates/intro.html', commands=commands)

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
                    self.data['summary']['failed'],
                    self.data['summary']['passed'],
                    '%.2f' % self.data['summary']['duration'],
                    self.data['created_at']]])))

def delete_old_data(old_data):
    for old_time, old_file in old_data:
        logging.debug('Deleting old file %s.', old_file)
        os.remove(old_file)
    

@OX_HERD_BP.route('/list_tests')
def list_tests():
    "Show list of available test results."

    master_file = cache_utils.get_path('test_master.pickle')
    if 1 or not os.path.exists(master_file):
        reprocess_master()
    if not os.path.exists(master_file):        
        raise Exception('No test master file found at %s' % master_file) #FIXME
    test_master = cache_utils.unpickle_name('test_master.pickle')
    return render_template(
        'test_list.html', title='Test List', test_data=test_master)


@OX_HERD_BP.route('/show_test')
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

@OX_HERD_BP.route('/scheduled_tests')
def scheduled_tests():
    my_tests = scheduling.SimpleScheduler.get_scheduled_tests()
    
