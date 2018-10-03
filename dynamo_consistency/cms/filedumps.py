"""
A module to handle file dumps from sites
"""


import os
import logging
import time
import datetime
import subprocess

from .. import config
from .. import opts

LOG = logging.getLogger(__name__)


class LineReader(object): # pylint:disable=too-few-public-methods
    """
    A class that translates lines from a file dump.
    It tracks the time that it was initialized.
    """

    def __init__(self):
        self.now = int(time.time())

    def __call__(self, line):
        """
        :param str line: Single line from a file dump
        :returns: The useful information from a line
        :rtype: tuple
        """

        contents = line.split()
        return contents[0], int(contents[2]), self.now


def read_ral_dump(endpoint, datestring=None):
    """
    Copies file from remote site and lists
    :param str endpoint: The SE to copy the file dump from
    :param str datestring: An optional datestring to force source file name
    :returns: A tuple of the filename and translator
    :rtype: tuple
    """

    inputfile = os.path.join(config.vardir('scratch'),
                             'dump_%s' % (config.SITE or opts.SITE_PATTERN))

    raw_file = '%s.raw' % inputfile
    if os.path.exists(raw_file):
        os.remove(raw_file)

    cp_command = ' '.join([
        'gfal-copy',
        '{endpoint}/store/accounting/dump_{date}'.format(
            endpoint=endpoint,
            date=datestring or datetime.datetime.utcnow().strftime('%Y%m%d')
            ),
        raw_file
    ])
    LOG.info('About to call: %s', cp_command)
    subprocess.check_call([cp_command], shell=True)

    sort_command = ' '.join(['sort', '-o', inputfile, raw_file])
    LOG.info('About to call: %s', sort_command)
    subprocess.check_call([sort_command], shell=True)

    return inputfile, LineReader()
