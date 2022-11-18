import random
import string
import kimai_util
import db_util
import mail
import argparse
import pathlib
from csv import DictReader
import traceback
import logging
from pathlib import Path


def create_user(firstname:str, lastname:str, email:str, usertype:str) -> None:
    usert = kimai_util.USER_TYPES[usertype]
    usr = (firstname[0] + firstname[-1] + lastname[:5]).lower()
    counter = 1
    while not db_util.check_username_free(usr):
        usr = usr + str(counter)
        counter += 1
    pwd = "".join(random.choices(string.ascii_letters + string.digits,k=12))
    kimai_util.console_user_create(usr, pwd, email, usert.roles)
    user_id = db_util.get_user_id(usr)
    for team in usert.teams:
        db_util.user_join_team(user_id, team)
    print(usr, pwd)
    logging.info(f"{usr} {pwd}")
    db_util.set_user_alias(usr, firstname, lastname)
    msg = mail.make_onboarding_msg(firstname, lastname, usert, usr, pwd)
    #attch = [ mail.get_absolute_path(s) for s in ["worktime_DE.pdf", "worktime_EN.pdf"]]
    mail.send_mail([email], "Details on worktime tracking", msg)


def create_from_dic(user, interactive):
    if interactive:
        while True:
            print("#"*20)
            print(user)
            ans = input("Create User? y for yes, n for skip")
            if ans == "y":
                try:
                    create_user(**user)
                    break
                except:
                    traceback.print_exc()
            if ans == "n":
                break
    else:
        logging.info("create user non interactive")
        logging.info(str(user))
        try:
            create_user(**user)
        except Exception as e:
            logging.exception(e)
            exit(-1)


def create_by_csv(filepath):
    with open(str(filepath), "r") as ifile:
        for user in DictReader(ifile, delimiter=","):
            create_from_dic(user, True)
                

if __name__ == "__main__":
    thisfile = Path(__file__)
    logging.basicConfig(filename=str(thisfile.parent.parent.resolve() / f"kimai2_autohire_{thisfile.stem}.log"),
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

    parser = argparse.ArgumentParser(description="onboard users either from csv or from command line")
    parser.add_argument("--file", dest="csvfile", default=None, help="Specify the file to create users from. If specified ignores other arguments.")
    parser.add_argument("userdata", nargs="*", help=f"create user from command line: Firstname, Lastname, emailaddr, Usertype[{'|'.join(kimai_util.USER_TYPES.keys())}]")
    parser.add_argument("--inter", action="store_true", help="wether or not to run interactive expecting further inpunt default = not set")

    args = parser.parse_args()
    args.userdata = ["fritz", "fratz", "fritz@web.de", "student"]
    if args.csvfile:
        print("Reading new users from csv file")
        fp = pathlib.Path(args.csvfile)
        if not fp.is_file():
            print("File could not be found!")
            exit(-1)
        create_by_csv(fp)
    elif args.userdata:
        dic = {
            "firstname" : str(args.userdata[0]),
            "lastname": str(args.userdata[1]), 
            "email": str(args.userdata[2]), 
            "usertype": str(args.userdata[3])
        }
        create_from_dic(dic, args.inter)
    else:
        parser.print_help()
