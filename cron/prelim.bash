#!/bin/bash

FLD="$HOME/kimai2-autohire"
source $FLD/venv/bin/activate
python3 $FLD/create_timesheet_kgl.py --preliminary --today