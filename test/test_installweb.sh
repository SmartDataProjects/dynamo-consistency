#! /bin/bash

if [ -d www ]
then

    rm -r www

fi

consistency-web-install

ec=0

for f in "dynamo.css" "explanations.html" "index.php" "output.html" "sorttable.js" "stats.db" "stylin.css"
do

    if [ ! -f "www/$f" ]
    then

        echo "Missing $f"
        ec=$(( $ec + 1 ))

    fi

done

exit $ec
