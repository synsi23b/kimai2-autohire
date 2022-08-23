#!/bin/bash

lxc exec kimai -- /root/export.bash

YEARLONG=`date +%Y`
YEAR=`date +%Y | cut -c 3,4`
MONTH=`date +%m`

SRC="/var/lib/lxd/containers/kimai/rootfs/home/ubuntu/export/*${MONTH}_${YEAR}*.xlsx"
DST="/media/softwareraid/nextcloud/__groupfolders/2/STUNDENZETTEL/$YEARLONG/$MONTH"
DSTP="/media/softwareraid/nextcloud/__groupfolders/2/STUNDENZETTEL/$YEARLONG"

mkdir -p $DST
cp $SRC $DST
chown -R 100033:100033 $DSTP

lxc exec nextcloud -- /root/occ.sh groupfolders:scan -q 2
