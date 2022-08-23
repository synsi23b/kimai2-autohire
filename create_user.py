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


def create_user(firstname:str, lastname:str, email:str, usertype:str, monthly_hours:float) -> None:
    usr = (firstname[0] + firstname[-1] + lastname[:5]).lower()
    counter = 1
    while not db_util.check_username_free(usr):
        usr = usr + str(counter)
        counter += 1
    pwd = "".join(random.choices(string.ascii_letters + string.digits,k=12))
    kimai_util.console_user_create(usr, pwd, email)
    print(usr, pwd)
    logging.info(f"{usr} {pwd}")
    db_util.set_user_alias(usr, firstname, lastname)
    kimai_util.create_activity(usertype, usr, monthly_hours)
    msg = mail.make_onboarding_msg(firstname, lastname, usertype, monthly_hours, usr, pwd)
    attch = [ mail.get_absolute_path(s) for s in ["worktime_DE.pdf", "worktime_EN.pdf"]]
    mail.send_mail([email], "Details on worktime tracking", msg, attch)


def create_from_dic(user, interactive):
    if interactive:
        while True:
            print("#"*20)
            user["monthly_hours"] = float(user["monthly_hours"])
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
        logging(str(user))
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
    parser.add_argument("userdata", nargs="*", help="create user from command line: Firstname, Lastname, emailaddr, Usertype, monthly_hours")
    parser.add_argument("--inter", action="store_true", help="wether or not to run interactive expecting further inpunt default = not set")

    args = parser.parse_args()
    if args.csvfile:
        print("Reading new users from csv file")
        fp = pathlib.Path(args.csvfile)
        if not fp.is_file():
            print("File could not be found!")
            exit(-1)
        create_by_csv(fp)
    else:
        dic = {
            "firstname" : str(args.userdata[0]),
            "lastname": str(args.userdata[1]), 
            "email": str(args.userdata[2]), 
            "usertype": str(args.userdata[3]), 
            "monthly_hours": float(args.userdata[5])
        }
        create_from_dic(dic, args.inter)
