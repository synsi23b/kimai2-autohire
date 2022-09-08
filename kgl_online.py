from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FireService
from webdriver_manager.firefox import GeckoDriverManager
#from selenium.webdriver.chrome.service import Service as ChromeService
#from webdriver_manager.chrome import ChromeDriverManager
import PyPDF2
import re
from time import sleep
from pathlib import Path
from datetime import datetime
from pyvirtualdisplay.smartdisplay import SmartDisplay


class WebPortal:
    def __init__(self, credentials):
        self._driver = None
        self._lastname = "none"
        self._screenfolder = Path(__file__).resolve().parent / "screenshots"
        self._creds = credentials
        self._disp = None
    
    def __enter__(self):
        self._disp = SmartDisplay()
        self._disp.start()
        self._driver = webdriver.Firefox(service=FireService(GeckoDriverManager().install()))
        #self._driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
        return self

    def __exit__(self, type, value, traceback):
        if self._driver is not None:
            self._driver.quit()
        self._disp.stop()

    def login(self):
        self._driver.get("https://kundenportal.klg-rhein-main.de/")
        # wait benutzer name
        elem = self._await_name("bn")
        elem.send_keys(self._creds["user"])
        # wait password
        elem = self._await_name("pw")
        elem.send_keys(self._creds["pass"])
        # press login button
        elem = self._await_name("login")
        self._screenshot()
        elem.click()

    def upload_timesheets(self, sheets_abspathstr:list, year, month):
        # switch to message center page
        elem = self._await_name("message")
        self._screenshot()
        elem.click()
        # go to new message screen
        elem = self._await_name("newMessage")
        self._screenshot()
        elem.click()
        # fill in subject with current year / month
        elem = self._await_name("subject")
        elem.send_keys(f"Stundenzettel {month} / {year}")
        # TODO sending the keys works, but they get appended to the original Message "mit freundlichen Gruessen.. "
        elem = self._driver.find_element(By.CLASS_NAME, "note-editable")
        #elem.send_keys(Keys.HOME)
        elem.send_keys(f"\n\n*Diese Nachricht wurde von unserer Zeiterfassungssoftware automatisiert versendet*")
        # switch to attachment screen by clicking little paperclip icon
        #elem = self._driver.find_element(By.CLASS_NAME, "fa-paperclip")
        # go to the list element containing the paperclip
        #elem = elem.find_element(By.XPATH, "./..")
        # TODO didnt work, using xpath from tab list parent and indexed location. Might break on UI layout change!
        elem = self._driver.find_element(By.XPATH, '//*[@name="tab"]/ul/li[3]')
        self._screenshot()
        elem.click()
        # open addfile pop up
        elem = self._await_name("AddFile")
        self._screenshot()
        elem.click()
        # transmit files to the page
        elem = self._await_name("file[]")
        for f in sheets_abspathstr:
            elem.send_keys(f)
            sleep(0.5)
            while(not elem.is_enabled()):
                sleep(0.5)
        self._screenshot("files")
        # close the file dialog and send the message
        #elem = self._await_name("Close")
        # there are multiple buttons called close :(
        elems = self._driver.find_elements(By.NAME, "Close")
        elem = None
        for elem in elems:
            if elem.text == 'Schließen':
                break
        elem.click()
        sleep(10)
        elem = self._await_name("send")
        self._screenshot()
        elem.click()
        sleep(10)
        self._screenshot("upload-completed")

    def download_salary_file(self, year, month):
        pass

    def _await_name(self, name, timeout=60):
        self._lastname = name
        return WebDriverWait(self._driver, timeout=timeout).until(lambda d: d.find_element(By.NAME, name))

    def _screenshot(self, override=""):
        # sleep to give the browser some time to build the ui before screenshoting
        sleep(1)
        sname = datetime.utcnow().strftime("%y_%m_%d-%H_%M_%S_%f-")
        if override != "":
            sname += override
        else:
            sname += self._lastname
        # take screenshot and store under name
        spath = str(self._screenfolder / sname) + ".png"
        print(spath)
        img = self._disp.waitgrab()
        img.save(spath)


def pdf_salary_extract(filepath, year, month):
    year = year % 100
    datenotmatch = True
    res = []
    # open the salary page
    # download the salary file
    # extract the data and form list
    with open(filepath, "rb") as inf:
        pdf = PyPDF2.PdfFileReader(inf)
        if len(pdf.pages) > 1:
            raise RuntimeError("KGL Webportal currently not supporting multi-page salary files")
        text = pdf.pages[0].extract_text()
        lines = text.split("\n")
        mapat = re.compile(r'\s+(\d+)\s+(.+),\s(.+?)\s+(\d?\.?\d{1,3}),(\d{2}).+')
        sumpat = re.compile(r'\s+Gesamtsumme:\s+(\d*\.?\d{1,3}),(\d{2})')
        datepat = re.compile(r'AN-Übersichten\slt\.\sZV-Art\s+MONAT\s+(\d{2})\/(\d{2}).+')
        sum = 0
        sumextract = 0
        for l in lines:
            mch = mapat.match(l)
            if mch:
                eu, ce = mch.group(4), int(mch.group(5))
                eu = int(eu.replace(".", ""))
                eurocent = eu * 100 + ce
                sum += eurocent
                res.append({
                    "original": l,
                    "pe": int(mch.group(1)),
                    "lastname": mch.group(2),
                    "firstname": mch.group(3),
                    "eurocent": eurocent
                })
            smch = sumpat.match(l)
            if smch:
                eu, ce = smch.group(1), int(smch.group(2))
                eu = int(eu.replace(".", ""))
                sumextract = eu * 100 + ce
            dmch = datepat.match(l)
            if dmch and int(dmch.group(1)) == month and int(dmch.group(2)) == year:
                datenotmatch = False
        if sumextract != sum:
            raise RuntimeError("Salary sum not matching")
        if datenotmatch:
            raise RuntimeError("Salary file is not fore the asked for month / year")
    return res


if __name__ == "__main__":
    pass
    #p = Path("./upfiles").glob('**/*')
    #files = [str(x.resolve()) for x in p if x.is_file()]
    #print(files)
    cred = {"user": "uname", "pass": "passw"}
    with WebPortal(cred) as kgl:
        kgl.login()
        sleep(10)
        kgl._screenshot()
        #kgl.upload_timesheets(files, 2022, 8)
    pass
    #fp = "C:/Users/mail/Downloads/435_11256_000_000000_202207_20220808_095638_AN-Übersichten lt  ZV-Art.PDF"
    #print(pdf_salary_extract(fp, 2022, 7))
    