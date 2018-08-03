"""
Module that handles the summary database and webpage.
It will install the summary webpage for you the first time you run the consistency check.
"""


import os
import json
import time
import sqlite3
import shutil
import logging


from docutils.core import publish_file

from . import config
from .backend import siteinfo
from .backend import check_site


LOG = logging.getLogger(__name__)


def install_webpage():
    """
    Installs files for webpage in configured **WebDir** if the directory doesn't exist yet.
    """

    webdir = config.config_dict()['WebDir']
    if os.path.exists(webdir):
        return

    os.mkdirs(webdir)

    sourcedir = os.path.join(os.path.dirname(__file__), 'web')

    # Files that should just be copied directly
    with open(os.path.join(sourcedir, 'files.txt')) as manifest:
        for line in manifest:
            shutil.copy(os.path.join(sourcedir, line.strip()), webdir)

    publish_file(source_path=os.path.join(sourcedir, 'explanations.rst'),
                 destination_path=os.path.join(webdir, 'explanations.html'))

    # Initialize summary table
    with open(os.path.join(sourcedir, 'maketables.sql'), 'r') as script_file:
        script_text = ''.join(script_file)

    conn = sqlite3.connect(os.path.join(webdir, 'stats.db'))

    conn.cursor().executescript(script_text)

    conn.commit()
    conn.close()


def _connect():
    """
    :returns: A connection to the summary database.

              .. note::

                 This connection needs to be closed by the caller

    :rtype: sqlite3.Connection
    """

    webdir = config.config_dict()['WebDir']
    dbname = os.path.join(webdir, 'stats.db')

    if not os.path.exists(dbname):
        install_webpage()

    return sqlite3.connect(dbname)


class NoMatchingSite(Exception):
    """
    For raising when consistency doesn't know what site to run on
    """
    pass


def pick_site(pattern=None):
    """
    This function also does the task of syncronizing the summary database with
    the inventory's list of sites that match the pattern.

    :param str pattern: A string that should be contained in the site name
    :returns: The name of a site that is ready and hasn't run in the longest time
    :rtype: str
    :raises NoMatchingSite: If no site matches or is ready
    """

    # First add sites that match our pattern
    sites = siteinfo.site_list()
    if pattern:
        sites = [site for site in sites if pattern in site]

    if not sites:
        raise NoMatchingSite('Cannot find a site that matches %s' % pattern)

    conn = _connect()
    curs = conn.cursor()

    curs.executemany(
        'INSERT OR IGNORE INTO sites VALUES (`?`, 0, 0, NULL)',
        [(site,) for site in sites]
        )

    # Now get the one that hasn't run in the longest time, and is good

    sites = set(sites)

    output = None

    for site, isrunning in curs.execute(
            """
            SELECT sites.site FROM sites
            LEFT JOIN stats ON sites.site=stats.site
            ORDER BY stats.entered ASC
            """):
        if site in sites and \
                (isrunning == 0 or isrunning == -1) and \
                check_site(site):
            output = site
            break

    # Lock selected site
    if output is not None:
        curs.execute('UPDATE sites SET isrunning = 1 WHERE site = ?', (output,))

    conn.commit()
    conn.close()

    if output is None:
        raise NoMatchingSite('No sites out of %s seem to be ready' % sites)

    return output


def is_debugged(site):
    """
    :returns: If the site is cleared for acting on consistency results
    :rtype: bool
    """

    conn = _connect()
    curs = conn.cursor()
    curs.execute('SELECT isgood FROM sites WHERE site = ?', (site, ))

    debugged = curs.fetchone()[0]

    conn.close()

    return debugged


# This definitely needs some overhaul
def update_summary(    #pylint: disable=too-many-arguments
        site, duration, numfiles, numnodes, numempty,
        nummissing, missingsize, numorphan, orphansize,
        numnosource, numunrecoverable,
        numunlisted, numbadunlisted,
        numunmerged=0, numlogs=0):
    """
    Update the summary webpage.

    :param str site: The site to update the summary for
    :param float duration: The amount of time it took to run, in seconds
    :param int numfiles: Number of files in the tree
    :param int numnodes: Number of directories listed
    :param int numempty: Number of empty directories to delete
    :param int nummissing: Number of missing files
    :param int missingsize: Size of missing files, in bytes
    :param int numorphan: Number of orphan files
    :param int orphansize: Size of orphan files, in bytes
    :param int numnosource: The number of missing files that are on no other disk
    :param int numunrecoverable: The number of missing files that are not on disk or tape
    :param int numunlisted: Number of directories that were not listed
    :param int numbadunlisted: Number of unlisted directories that were not listed due to error
    :param int numunmerged: Number of files to remove from unmerged (CMS only)
    :param int numlogs: Number of unmerged files that were logs (CMS only)
    :returns: True if the summary table was updated
    :rtype: bool
    """

    conn = _connect()
    curs = conn.cursor()

    curs.execute('INSERT INTO stats_history SELECT * FROM stats WHERE site=?', (site, ))

    is_dst = time.localtime().tm_isdst
    if is_dst == -1:
        LOG.error('Daylight savings time not known. Times on webpage will be rather wrong.')

    config_dict = config.config_dict()

    curs.execute(
        """
        REPLACE INTO stats
        (`site`, `time`, `files`, `nodes`, `emtpy`, `cores`, `missing`, `m_size`,
         `orphan`, `o_size`, `entered`, `nosource`, `unlisted`, `unmerged`, `unlisted_bad`,
         `unrecoverable`, `unmergedlogs`)
        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATETIME(DATETIME(), "-{0} hours"), ?, ?, ?, ?, ?, ?)
        """.format(5 - is_dst),
        (site, duration, numfiles, numnodes, numempty,
         config_dict.get('NumThreads', config_dict.get('MinThreads', 0)),
         nummissing, missingsize, numorphan, orphansize,
         numnosource, numunlisted, numunmerged, numbadunlisted,
         numunrecoverable, numlogs))

    conn.commit()
    conn.close()

    return True


def _webdir():
    """
    If the web directory does not exist, this function installs it
    :returns: The web directory location
    :rtype: str
    """

    webdir = config.config_dict()['WebDir']
    if not os.path.exists(webdir):
        install_webpage()

    return webdir


def move_local_files(site):
    """
    Move files in the working directory to the web page
    :param str site: The site which has files ready to move
    """

    # All of the files and summary will be dumped here
    webdir = _webdir()

    # If there were permissions or connection issues, no files would be listed
    # Otherwise, copy the output files to the web directory
    for filemid in ['missing_datasets',
                    'missing_nosite',
                    'compare_missing',
                    'compare_orphan',
                    'unrecoverable',
                    'unmerged']:

        filename = '%s_%s.txt' % (site, filemid)

        if os.path.exists(filename):
            shutil.move(filename, webdir)
        else:
            LOG.warning('%s not present in working directory, removing from summary web page',
                        filename)

            to_rm = os.path.join(webdir, filename)
            if os.path.exists(to_rm):
                os.remove(to_rm)


def update_config():
    """
    Updates the configuration file at the summary website
    """
    webdir = _webdir()

    webconf = os.path.join(webdir, 'consistency_config.json')

    if webconf == config.LOCATION:
        return

    with open(webconf, 'r') as webfile:
        webdict = json.load(webfile)

    with open(config.LOCATION, 'r') as runfile:
        rundict = json.load(runfile)

    if rundict != webdict:
        shutil.copy(config.LOCATION, runfile)


def unlock_site(site):
    """
    Sets the site running status back to 0
    :param str site: Site to unlock
    """
    conn = _connect()
    conn.cursor().execute('UPDATE sites SET isrunning = 0 WHERE site = ?', (site,))
    conn.commit()
    conn.close()
