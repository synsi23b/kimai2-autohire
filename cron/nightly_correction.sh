#!/bin/bash

FLD="$HOME/kimai2-autohire"
source $FLD/venv/bin/activate
python3 $FLD/nightly_timesheet_update.py
