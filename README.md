# kimai2-autohire

programmed against kimai version 1.21

# setup
## create second database for keeping own records on kimai host
```sql
mysql> create database dbautohire;
mysql> grant all privileges on dbautohire.* to kimai@localhost with grant option;
mysql> flush privileges;
```