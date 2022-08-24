from difflib import diff_bytes
import sys

from selenium import webdriver
import os
from PIL import Image
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from concurrent.futures import ThreadPoolExecutor
import hashlib
import random
import queue
import threading
import traceback
import re
import filelock

#31
#/ 60
engines_re = r"(\d+)\n/ (\d+)"

def fullpage_screenshot(driver, name, file, from_=""):

        print(f"Starting chrome full page screenshot workaround ... {driver.current_url}. From {from_}")

        total_width = driver.execute_script("return document.body.offsetWidth")
        total_height = driver.execute_script("return document.body.parentNode.scrollHeight")
        viewport_width = driver.execute_script("return document.body.clientWidth")
        viewport_height = driver.execute_script("return window.innerHeight")
        #print("Total: ({0}, {1}), Viewport: ({2},{3})".format(total_width, total_height,viewport_width,viewport_height))
        rectangles = []

        i = 0
        while i < total_height:
            ii = 0
            top_height = i + viewport_height

            if top_height > total_height:
                top_height = total_height

            while ii < total_width:
                top_width = ii + viewport_width

                if top_width > total_width:
                    top_width = total_width

                #print("Appending rectangle ({0},{1},{2},{3})".format(ii, i, top_width, top_height))
                rectangles.append((ii, i, top_width,top_height))

                ii = ii + viewport_width

            i = i + viewport_height

        stitched_image = Image.new('RGB', (total_width, total_height))
        previous = None
        part = 0

        for rectangle in rectangles:
            if not previous is None:
                driver.execute_script("window.scrollTo({0}, {1})".format(rectangle[0], rectangle[1]))
                #print("Scrolled To ({0},{1})".format(rectangle[0], rectangle[1]))
                time.sleep(0.2)

            file_name = f"part_{name}{part}.png"
            #print("Capturing {0} ...".format(file_name))

            driver.get_screenshot_as_file(file_name)
            screenshot = Image.open(file_name)

            if rectangle[1] + viewport_height > total_height:
                offset = (rectangle[0], total_height - viewport_height)
            else:
                offset = (rectangle[0], rectangle[1])

            #print("Adding to stitched image with offset ({0}, {1})".format(offset[0],offset[1]))
            stitched_image.paste(screenshot, offset)

            del screenshot
            os.remove(file_name)
            part = part + 1
            previous = rectangle

        stitched_image.save(file, optimize=True, quality=95)
        #print("Finishing chrome full page screenshot workaround...")
        return stitched_image

def setUp():
    os.putenv('PREDEF_FILE', os.path.abspath("name.socket"))
    os.environ['PREDEF_FILE'] = os.path.abspath("name.socket")
    options = webdriver.ChromeOptions()
    PROXY = "socks5://127.0.0.1:9050" # IP:PORT or HOST:PORT
    options.add_argument('--proxy-server=%s' % PROXY)
    options.add_argument("disable-infobars"); # disabling infobars
    options.add_argument("--disable-extensions"); # disabling extensions
    options.add_argument("--disable-gpu"); # applicable to windows os only
    options.add_argument("--disable-dev-shm-usage"); # overcome limited resource problems
    options.add_argument("--no-sandbox"); #Bypass OS security model
    options.add_experimental_option("excludeSwitches",["ignore-certificate-errors"])
    options.add_argument('--headless')
    options.add_argument('window-size=1200x1000')
    path = os.path.join(os.path.dirname(__file__), "chromedriver")
    
    driver = webdriver.Chrome(path, options=options)

    return driver

def check_files(files):

    WORKERS_NUMBER = int(os.environ.get("NO_WORKERS", "12"))

    worklist = queue.Queue()

    prev = {}

    def process():

        while True:
            s = worklist.qsize()
            if s == 0:
                print("Worklist empty, returning")
                break

            filename = worklist.get()
            worklist.task_done()
            print("Work count", s)
            times = 0        
            driver = setUp()

            done = False
            while times < 2:
                try:
                    check_file(driver, filename, prev = prev)        
                    print(f"{i}/{len(files)} {filename}")
                    done = True
                    break
                except Exception as e:
                    print(e)
                    print(traceback.format_exc())
                    if "net::ERR_PROXY_CONNECTION_FAILED" in traceback.format_exc():
                        print("Trying to access file")
                        with filelock.FileLock("name.socket.lock"):
                            # Restart proxy
                            print("Restarting")
                            f = open("name.socket", 'r+')
                            content = f.read()
                            if not "RESTART" in content:
                                f.seek(0)
                                f.write("RESTART")
                                f.close()
                            else:
                                print("Already restarting tor")

                            # Give time to restart
                            time.sleep(3 + 0.01*random.randint(1, 300))
                    times += 1
            if not done:
                # requeue the page
                worklist.put(filename)

    C = 0
    C2 = 0
    for i, filename in enumerate(files):
        # Check if exist
        content = open(filename, "rb").read()
        hash = hashlib.sha256(content).hexdigest()
        if os.path.exists(f"out/{hash}.wasm.logs.txt"):
            print(f"{C} File {filename} already checked")
            C += 1
            continue 
        C2 += 1
        if C2 % 100 == 99:
            print(f"{C2}/{len(files)}")
        worklist.put(filename)

    print(f"Files count {worklist.qsize()}. Launching {WORKERS_NUMBER} workers")

    workers = []
    for _ in range(WORKERS_NUMBER):
        th = threading.Thread(target=process)
        workers.append(th)
        th.start()

    for th in workers:
        th.join()

    #for j in jobs:
    #    j.result()
        

def expand_element(driver, element, visited):
    subelements  = element.find_elements(By.XPATH, "./*")
    tag = element.get_attribute('tagName')    
    class_ = element.get_attribute('class')

    text = element.text
    tags_to_skip= ["TEMPLATE" , "svg" , "g" ,"path" , "STYLE" , "img" , "video"  ]
    S =""
    
    if tag in tags_to_skip:
        return S
    S += f"tag: {tag}\n"
    S += f"class: {class_}\n"
    S += f"{text}\n"
    
    return S
    #shadowroot = expand_shadow_element(element)
    #if shadowroot:
     #   subelements  = shadowroot.find_elements(By.XPATH, "./*")

    #for obj in subelements:
    #    expand_element(obj, fd, visited)    

def expand_shadow_element(driver, element):
    try:
        shadow_root = driver.execute_script('return arguments[0].shadowRoot', element)
        return shadow_root
    except Exception as e:
        print(e)
        return None

def break_if_captcha(driver, name):
    #image = fullpage_screenshot(driver, name, f"snapshots/{name}.analysis.png")

    if "captcha" in driver.current_url:

        print("Trying to access file")
        with filelock.FileLock("name.socket.lock"):
            print("Restarting")
            f= open("name.socket", 'r+')
            content = f.read()
            if not "RESTART" in content:
                f.seek(0)
                f.write("RESTART")
                f.close()
            else:
                print("Already restarting tor")
            raise Exception("Blocked. Restarting tor ?") 


def check_file(driver, filename, prev = {}, out="out"):
    name = os.path.basename(filename)
   
    url = "https://www.virustotal.com/gui/home/upload"
    driver.delete_all_cookies()


    print(f"Taking {name}")
    driver.get(url)
    
    # To avoid bot
    # . time.sleep(random.randint(1,3))
    break_if_captcha(driver, name)
    times = 0
    print("Waiting for upload btn")
    while True:
        time.sleep(0.34)
        times += 1

        if times >= 500:
            print("Restarting")
            raise Exception("Too many times")
        # Detect where the button is
        # #infoIcon
        break_if_captcha(driver, name)
        # fullpage_screenshot(driver, name, f"snapshots/{name}.upload.png",from_="Waiting from upload btn")
        try:
            inpt = driver.execute_script("return document.querySelector('vt-ui-shell').querySelector('#view-container home-view').shadowRoot.querySelector('vt-ui-main-upload-form').shadowRoot.querySelector('#fileSelector')")
            break
        except: 
            #print(traceback.format_exc())

            pass
    driver.execute_script("arguments[0].style.display = 'block';", inpt)
    #print(inpt)
    inpt.send_keys(os.path.abspath(filename))

    time.sleep(2)
    # Now confirm the upload if needed
    times = 0
    print("Checking if confirm button")
    while True:
        if "file" in driver.current_url:
            break
        time.sleep(0.05)
        break_if_captcha(driver, name)
        # fullpage_screenshot(driver, name, f"snapshots/{name}.upload2.png",from_="Waiting from confirming btn")

        try:
            btn = driver.execute_script("return document.querySelector('vt-ui-shell').querySelector('#view-container home-view').shadowRoot.querySelector('vt-ui-main-upload-form').shadowRoot.querySelector('#confirmUpload')")
            if btn:
                print("Confirming upload")
                driver.execute_script("arguments[0].click();", btn)
                break
            times += 1
            if times > 1000:
                break
        except Exception as e:
            print(e) 
            print(traceback.format_exc())

            pass

    content_text = ""

    time.sleep(4)
    print("Wait for the analysis")
    times = 0
    while "/file-analysis/" in driver.current_url:
        times += 1

        if times >= 300:
            raise Exception("Too many times")

        break_if_captcha(driver, name)
        time.sleep(1)
        print("Yet analysing...", driver.current_url)
        content = driver.find_element(By.TAG_NAME, 'body')
        content_text = expand_element(driver, content, {})
        # image = fullpage_screenshot(driver, name, f"wrong/{name}.analysis.png",from_="Waiting from analysis")


    times = 0
    print("Getting info from file hash address",driver.current_url)
    while "/file/" not in driver.current_url:
        break_if_captcha(driver, name)
        print(driver.current_url, times)
        time.sleep(0.6)   
        times += 1
        if times >= 1000: #600s
            raise Exception("Wait too much") 
    
    #time.sleep(2)
    # / 54
    if "file" in driver.current_url:
        times = 0
        while True:
            time.sleep(0.3)
            break_if_captcha(driver, name)
            # Done
            content = driver.find_element(By.TAG_NAME, 'body')
            content_text = expand_element(driver, content, {})
            times += 1
            if times >= 2000: # 600s 10mins
                raise Exception("Waiting too much")

            matches = re.findall(engines_re, content_text)
            if matches:
                print("Analysis", name, matches, times)
                positives = matches[0][0]
                positives = int(positives)
                all = matches[0][1]
                all = int(all)

                if (all >= 59 or "Security Vendors' Analysis" in content_text) and "Analysing (" not in content_text:
                    print("Returning")
                    time.sleep(2)
                else:
                    continue

                fd = open(f"{out}/{name}.logs.txt", "w")
                fd.write(content_text)
                fd.close()
                image = fullpage_screenshot(driver, name, f"{out}/{name}recogn.png",from_="Waiting from file hash")
                print(f"Done {name}")
                return
       

    print("Wrong result")
    #time.sleep(3)
    image = fullpage_screenshot(driver, name, f"wrong/{name}wrong.png",from_="wrong result")
    raise Exception("Wrong result")

if __name__ == "__main__":
    files = os.listdir(sys.argv[1])
    files = [f"{sys.argv[1]}/{f}" for f in files if f.endswith(".wasm")]
    check_files(files)