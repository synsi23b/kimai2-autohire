#!/bin/bash

FLD="$HOME/kimai2-autohire"
source $FLD/venv/bin/activate
python3 $FLD/breaktime_saldo_updates.py
