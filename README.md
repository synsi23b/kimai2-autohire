# kimai2-autohire

programmed against kimai version 1.21

# setup

## create second database for keeping own records on kimai host

*not yet used*

```sql
mysql> create database dbautohire;
mysql> grant all privileges on dbautohire.* to kimai@localhost with grant option;
mysql> flush privileges;
```
## basic setup
1. after cloning into home directory, install requirements in a virtual environment called venv
```bash
virtualenv venv
source venv/bin/activate
pip3 install -r requirements.txt
```
2. some information like the database and email information gets read from the kimai env file, so make sure kimai is in the default path */var/www/kimai2* and its environment file is populated
3. setup crontabs to run for a user that can read the kimai env file, for an example see work-life-checker.


# Work-Life-Checker

The worklife checker can calculate the sum of working hours over each week for the last 5 weeks. It counts from monday to sunday regardless of the day it is executed, therefore should be idialy run on Sunday night, just before beginning of the next week.

The scripts sends a worktime report to every user checked. If it ddetects that a user spend 10 hours more than their regular weekly time, it will also send this report to the supervisors.

This is an example integration with the system root corntab, to run the worklife balance check every sunday night at 23:24 of system time.
```bash
24 23 * * 0 sudo -u ubuntu /home/ubuntu/kimai2-autohire/cron/worklife_check.bash
```

To setup the script, copy the file worklife.yaml from the cron folder to the home directory.
```bash
cp kimai2-autohire/cron/worklife.yaml /home/ubuntu/
```
And fill in which users to check and to which supervisors to send mails if an alarm is triggered.
The configuration works like thios: 
one entry per line, key-value pairs.

- if the entry is an email-address, it is a supervisor-email that gets send alerts. multiple supervisors can be defined. there is no meaning to the value attached to the supervisor, so just set it to 1 for now.

- if the entry is a number, it is interpreted as the user id from the database to check. the value section is the nominal worktime per week for that user in hours. To get a list of users and ID execute the following sql.
```sql
mysql> USE kimaidb;
mysql> SELECT id, username, alias FROM kimai2_users;
```