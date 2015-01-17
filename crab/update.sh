#! /bin/bash

# This is a nice little script that submits jobs for me, cleans up my space, and updates the website

# This is where I am keeping all of the output:
STOREDIR='/scratch/dabercro/ConsistencyCheck/crabRuns'
FAILDIR='/home/dabercro/ConsistencyCheck/FailedCheck'
SERVERDIR='/home/cmsprod/public_html/ConsistencyChecks'

# "T2_US_Nebraska" is not working, because they are naughty. i.e. not my fault, apparently.
declare -a SITES=("T2_US_Caltech" "T2_US_Florida" "T2_US_MIT" "T2_US_Purdue" "T2_US_UCSD" "T2_US_Vanderbilt" "T2_US_Wisconsin")

for SITE in "${SITES[@]}";do
    COUNTDIR=`ls -d $SITE-* | wc -l`
    if [ "$COUNTDIR" -eq "1" ]; then                             # Ideally, there will only be one directory per site
        DIRNAME=`ls -d $SITE-*`
        echo $DIRNAME
        DIRCHECK=`ls $DIRNAME/res | wc -l`                       # Check if any results have been posted
        if [ "$DIRCHECK" -eq "0" ]; then                         # If not, try to retrieve output
            ./check.sh $DIRNAME
        fi
        ISTAR=`ls $DIRNAME/res/$SITE.tar*.gz | wc -l`            # Look for the tarred output
        if [ "$ISTAR" -eq "1" ]; then                            # If it's there, update the website
            cd $DIRNAME/res                                      # cd into the .tar directory
            tar -xzvf $SITE.tar*.gz                              # Getting tar stuff out
            if [ ! -d "$SERVERDIR/$SITE" ]; then                 # Make sure the right folder is there
                echo "It looks like it's the first time for $SITE."
                echo "Making a new folder!"                      # If not there, then make it
                mkdir $SERVERDIR/$SITE
            fi
            cp $SITE*results.txt $SERVERDIR/$SITE/.              # Put results on the server
            cp $SITE*summary.txt $SERVERDIR/$SITE/.              # Put summary on server to be read
            rm $SITE*.json $SITE*.txt                            # Clean up the stuff from tar
            cd -                                                 # Now cd back
            mv $SITE-* $STOREDIR/.                               # Now store that stuff
        elif [ "$ISTAR" -eq "0" ]; then                          # If there's no tar, check to see if the job finished
            if [ -f $DIRNAME/res/CMSSW_1.stdout ]; then          # If it did (with no tar) then there must have been an error
                echo "Looks like the job failed... Check that out later."
                cp -r $DIRNAME $STOREDIR/.                       # Store for long term
                mv $DIRNAME $FAILDIR/.                           # Also store in a place specfically for debugging
            fi
        else
            echo "How did I get more tars??"                     # This would be a rather weird thing to happen
            echo "I'll just hide those and start over!"
            mv $DIRNAME $STOREDIR/.                              # But no need to throw it out
        fi
    else
        if [ "$COUNTDIR" -gt "1" ]; then                         # If more than one directory for a site
            echo "There are too many directories from $SITE!!"   # Something odd happened
            echo "I'll just hide those and start over!"          # I don't want to worry about that right now
            mv $SITE-* $STOREDIR/.
        fi
        NOW=`date +"%Y-%m-%d-%T"`                                # Otherwise, there is no directory for a site
        echo ./submit.sh $SITE $NOW                              # It's easy to make a directory though
        ./submit.sh $SITE $NOW                                   # Submits a job here
    fi
done

python updateList.py -D $SERVERDIR                               # Updates the site list used by the website
cd $SERVERDIR
chmod 644 */*.txt                                                # Allow all files to be read by people outside the server
cd -