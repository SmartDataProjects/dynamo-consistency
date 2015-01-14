#!/bin/bash
#---------------------------------------------------------------------------------------------------
# Execute one job (works interactively and when executed in condor)
#---------------------------------------------------------------------------------------------------
# find the line to this dataset and do further analysis
echo ""
echo " START run.sh"
echo ""
echo " -=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-";
echo " -=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-";
echo ""

echo "###########################################"
echo "id:"
echo "###########################################"
id
echo "###########################################"
echo "hostname:"
echo "###########################################"
hostname
echo "###########################################"
echo "pwd:"
echo "###########################################"
pwd
echo "###########################################"
echo "ls -lhrt:"
echo "###########################################"
ls -lhrt

python ConsistencyCheck.py -c tempConfig.cfg

echo "###########################################"
echo "ls -lhrt:"
echo "###########################################"
ls -lhrt

#
echo ""
echo " -=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-";
echo " -=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-.-=o=-";
echo " END run.sh"
echo ""
exit $?;
