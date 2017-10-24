#! /bin/bash

SITE=$1

if [ -z "$SITE" -o "$SITE" = "-h" -o "$SITE" = "--help" ]
then
    perldoc -T $0
    exit 0
fi

case $SITE in 
    *["'"';']* ) exit 1 ;;
esac

# Add jq to the system path
PATH=$PATH:/home/dabercro/bin

# Get the directory of this script (should be in prod)
HERE=$(cd $(dirname $0) && pwd)

# Determine the SQLite3 database location from the configuration file
DATABASE=$(jq -r '.WebDir' $HERE/consistency_config.json)/stats.db

# If not running, quit
if [ "$(echo "SELECT isrunning FROM sites where site = '$SITE';" | sqlite3 $DATABASE)" != "2" ]
then

    echo "Site not running anymore"
    exit 1

fi

# Otherwise, kill

# First get all the processes from run_checks
for check_pid in $(pgrep run_checks.sh)
do

    compare_pid=$(pgrep -P $check_pid)

    # Check the compare.py calls for the site
    if grep $SITE /proc/$compare_pid/cmdline
    then

        # Kill the child processes
        echo pkill -P $compare_pid
        # Kill the process
        echo kill $compare_pid
        break

    fi

done

exit 0

# Wait for process to stop
while [ "$(echo "SELECT isrunning FROM sites where site = '$SITE';" | sqlite3 $DATABASE)" != "0" ]
do

    sleep 1

done

# Mark as unrunnable

echo "UPDATE sites SET isrunning = -1 WHERE site = '$SITE';" | sqlite3 $DATABASE

exit 0

: <<EOF

=pod

=head1 Usage:

   kill_and_disable.sh <SITE>

Determines if a site is being compared at the moment.
If it is, kill all the associated processes and wait.

Once there's nothing running for that site,
set the site to be not runnable until things are figured out.

=head1 Author

Daniel Abercrmbie <dabercro@mit.edu>

=cut

EOF
