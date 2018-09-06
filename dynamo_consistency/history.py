"""
Handles the invalidation of files through a separate read-write process
"""

import os
import sqlite3

from . import config


RUN = 0


def _connect():
    """
    :returns: A connection to the consistency database, along with a cursor.
              It creates the invalid table, if needed.

              .. note::

                 This connection needs to be closed by the caller

    :rtype: sqlite3.Connection, sqlite3.Cursor
    """

    dbname = os.path.join(config.vardir('db'), 'consistency.db')

    new = not os.path.exists(dbname)

    conn = sqlite3.connect(dbname)
    curs = conn.cursor()

    if new:
        with open(os.path.join(os.path.dirname(__file__),
                               'report_schema.sql'), 'r') as script_file:
            script_text = ''.join(script_file)

        curs.executescript(script_text)

    return conn, curs


def start_run():
    """
    Called in :py:func:dynamo_consistency.main.main`
    to register the start of a consistency run
    """

    global RUN # pylint: disable=global-statement

    conn, curs = _connect()

    curs.execute('INSERT OR IGNORE INTO sites (name) VALUES (?)',
                 (config.SITE, ))
    curs.execute("""
                 INSERT INTO runs (site)
                 SELECT rowid FROM sites WHERE name = ?
                 """, (config.SITE, ))

    curs.execute("""
                 SELECT runs.rowid FROM runs
                 LEFT JOIN sites ON sites.rowid = runs.site
                 WHERE sites.name = ?
                 ORDER BY runs.rowid DESC
                 LIMIT 1
                 """, (config.SITE, ))

    RUN = curs.fetchone()[0]

    conn.commit()
    conn.close()


def finish_run():
    """
    Called in :py:func:dynamo_consistency.main.main`
    to register the end of a consistency run
    """

    global RUN # pylint: disable=global-statement
    conn, curs = _connect()

    curs.execute("""
                 UPDATE runs SET finished = DATETIME('NOW', 'LOCALTIME')
                 WHERE rowid = ?
                 """, (RUN, ))

    RUN = None

    conn.commit()
    conn.close()


def _insert_directories(curs, files):
    """
    Inserts the directories into the proper table, given a cursor.

    :param sqlite3.Cursor curs: a cursor object to make the query
    :param list files: List of file, size tuples
    """

    directories = set([os.path.dirname(name) for name, _ in files])
    curs.executemany('INSERT OR IGNORE INTO directories (name) VALUES (?)',
                     [(dirname, ) for dirname in directories])


def _current_siteid(curs):
    """
    Get the site ID from the database

    :param sqlite3.Cursor curs: A cursor from the database to read
    :returns: The ID of the site
    :rtype: int
    """
    if not RUN:
        return None

    curs.execute('SELECT rowid FROM sites WHERE name = ?', (config.SITE, ))
    return curs.fetchone()[0]


def _report_files(table, files):
    """
    Reports to either invalid table or orphan table.
    Moves old files to the history table if they haven't been acted on yet.

    :param str table: Which table to use
    :param list files: Tuples of name, size of files to report
    """

    conn, curs = _connect()

    _insert_directories(curs, files)
    siteid = _current_siteid(curs)

    # Copy into history
    curs.execute(
        """
        INSERT INTO {table}_history
        (site, run, directory, name, size, entered, acted)
        SELECT site, run, directory, {table}.name, size, entered, 0
        FROM {table}
        WHERE {table}.site = ? AND {table}.run != ?
        """.format(table=table), (siteid, RUN))
    # Remove old entries
    curs.execute(
        """
        DELETE FROM {table}
        WHERE {table}.site = ? AND {table}.run != ?
        """.format(table=table), (siteid, RUN))

    curs.executemany(
        """
        INSERT INTO {table} (site, run, directory, name, size)
        VALUES (?, ?, (SELECT rowid FROM directories WHERE name = ?), ?, ?)
        """.format(table=table),
        [(siteid, RUN, os.path.dirname(name),
          os.path.basename(name), size)
         for name, size in files])

    conn.commit()
    conn.close()


def _get_files(table, site, acting):
    """
    Get list of files for a site from a given table.

    :param str table: Table to read from
    :param str site: Name of a site to get files for
    :param bool acting: Whether or not the caller is acting on the files
    :returns: The LFNs from the table
    :rtype: list
    """

    conn, curs = _connect()

    curs.execute(
        """
        SELECT directories.name, {table}.name FROM {table}
        LEFT JOIN sites ON sites.rowid = {table}.site
        LEFT JOIN directories ON directories.rowid = {table}.directory
        WHERE sites.name = ?
        ORDER BY directories.name, {table}.name
        """.format(table=table), (site, ))

    output = list([os.path.join(directory, out) for directory, out in curs.fetchall()])

    if acting:
        curs.execute(
            """
            INSERT INTO {table}_history
            (site, run, directory, name, size, entered, acted)
            SELECT site, run, directory, {table}.name, size,
                   entered, DATETIME('NOW', 'LOCALTIME')
            FROM {table}
            LEFT JOIN sites ON sites.rowid = {table}.site
            WHERE sites.name = ?
            """.format(table=table), (site, )
            )
        curs.execute(
            """
            DELETE FROM {table}
            WHERE site IN (
              SELECT rowid FROM sites
              WHERE sites.name = ?
            )
            """.format(table=table), (site, ))

    conn.commit()
    conn.close()

    return output


def report_missing(missing):
    """
    Stores a list of missing files in the invalidation table
    :param list missing: A list of tuples, where each tuple is a name, size pair
    """
    _report_files('invalid', missing)


def missing_files(site, acting=False):
    """
    Get the missing files from the consistency database.
    If the caller identifies itself as acting on the list,
    the list is moved into the history with the acted flag `True`.

    :param str site: Name of a site to get missing files for
    :param bool acting: Whether or not the caller is acting on the files
    :returns: The LFNs that were missing
    :rtype: list
    """
    return _get_files('invalid', site, acting)


def report_orphan(orphan):
    """
    Stores a list of orphan files in the orphan table
    :param list orphan: A list of tuples, where each tuple is a name, size pair
    """
    _report_files('orphans', orphan)


def orphan_files(site, acting=False):
    """
    Get the orphan files from the consistency database.
    If the caller identifies itself as acting on the list,
    the list is moved into the history with the acted flag `True`.

    :param str site: Name of a site to get orphan files for
    :param bool acting: Whether or not the caller is acting on the files
    :returns: The LFNs that were orphan
    :rtype: list
    """
    return _get_files('orphans', site, acting)


def report_unmerged(unmerged):
    """
    Stores a list of deletable unmerged files in the orphan table
    :param list unmerged: A list of tuples, where each tuple is a name, size pair
    """
    _report_files('unmerged', unmerged)


def unmerged_files(site, acting=False):
    """
    Get the deletable unmerged files from the consistency database.
    If the caller identifies itself as acting on the list,
    the list is moved into the history with the acted flag `True`.

    :param str site: Name of a site to get unmerged files for
    :param bool acting: Whether or not the caller is acting on the files
    :returns: The LFNs in unmerged that are deletable
    :rtype: list
    """
    return _get_files('unmerged', site, acting)


def report_empty(directories):
    """
    Adds emtpy directories to history database
    :param list directories: A list of director names
    """
    conn, curs = _connect()

    siteid = _current_siteid(curs)
    table = 'empty_directories'

    # Copy into history
    curs.execute(
        """
        INSERT INTO {table}_history
        (site, run, name, entered, acted)
        SELECT site, run, {table}.name, entered, 0
        FROM {table}
        WHERE {table}.site = ? AND {table}.run != ?
        """.format(table=table), (siteid, RUN))
    # Remove old entries
    curs.execute(
        """
        DELETE FROM {table}
        WHERE {table}.site = ? AND {table}.run != ?
        """.format(table=table), (siteid, RUN))

    curs.executemany(
        """
        INSERT INTO {table} (site, run, name)
        VALUES (?, ?, ?)
        """.format(table=table),
        [(siteid, RUN, name) for name in directories])

    conn.commit()
    conn.close()


def emtpy_directories(site, acting=False):
    """
    Get the list of empty directories.
    If acting on them, the directories are moved into the history database.

    :param str site: Name of a site to get empty directories for
    :param bool acting: Whether or not the caller is acting on the list
    :returns: The directory list
    :rtype: list
    """
    conn, curs = _connect()

    table = 'empty_directories'

    curs.execute(
        """
        SELECT {table}.name FROM {table}
        LEFT JOIN sites ON sites.rowid = {table}.site
        WHERE sites.name = ?
        ORDER BY {table}.name DESC
        """.format(table=table), (site, ))

    output = [out[0] for out in curs.fetchall()]

    if acting:
        curs.execute(
            """
            INSERT INTO {table}_history
            (site, run, name, entered, acted)
            SELECT site, run, {table}.name,
                   entered, DATETIME('NOW', 'LOCALTIME')
            FROM {table}
            LEFT JOIN sites ON sites.rowid = {table}.site
            WHERE sites.name = ?
            """.format(table=table), (site, )
            )
        curs.execute(
            """
            DELETE FROM {table}
            WHERE site IN (
              SELECT rowid FROM sites
              WHERE sites.name = ?
            )
            """.format(table=table), (site, ))

    conn.commit()
    conn.close()

    return output