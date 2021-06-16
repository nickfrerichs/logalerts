
import os,sys
import traceback
import json
import time
import shutil
import smtplib
from email.mime.text import MIMEText
import email
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import dynamicstate
import config
import output as out

class Logmonitor:

    # These class variables, shared by all objects. Put instance variables in __init__
    state_root_path = config.STATE_ROOT_PATH
    mail_server = config.MAILSERVER

    max_emails = 50
    max_email_length = 1048576

    current_timestamp = int(time.time())
    
    def __init__(self):

        try:
            self.debug_modules = config.DEBUG_MODULES
        except AttributeError:
            self.debug_modules = False

        try:
            self.email_all_monitors_to = config.EMAIL_ALL_MONITORS_TO
        except AttributeError:
            self.email_all_monitors_to = None

        try:
            self.force_recipient = config.FORCE_RECIPIENT
        except AttributeError:
            self.force_recipient = None

        self.cfg = {}
        self.runtimes = {}
        self.enabled = True
        self.state = {}
        self.dstate = None
        self.__load_state()
        self.queued_emails = list()
        self.check_count = 0
        
    # Decorator to be used to keep track of how long functions take
    def __trackruntime(totaltime):
        def inner(func):
            def wrapper(self, *args, **kwargs):
                start_time = time.time()
                value = func(self, *args, **kwargs)
                if self.runtimes.get(totaltime) is None:
                    self.runtimes[totaltime] = 0
                self.runtimes[totaltime] += time.time() - start_time
                return value
            return wrapper
        return inner


    def __load_state(self):
        state_path = os.path.join(self.state_root_path,self.__class__.__name__)

        try:
            with open(state_path) as f:
                self.state = json.load(f)
        except FileNotFoundError:
            self.state = {
                "monitor_name" : self.__class__.__name__,
                "_dynamic_state" : {}
            }

        if self.state.get("_dynamic_state") is None:
            self.dstate = dynamicstate.DynamicState({})

        else:
            self.dstate = dynamicstate.DynamicState(self.state["_dynamic_state"])


    def load_config(self, cfg):
        self.cfg = cfg
        try:
            self.init_cfg()
        except AttributeError:
            pass
        except BaseException as e:
            if self.debug_modules:
                raise e
            self.print_error(e)
            self.enabled = False
        

    def init_state(self, data=dict()):
        for key in data:
            if self.state.get(key) is None:
                self.state[key] = data[key]


    def save_state(self):
        if self.enabled:
            if os.path.exists(self.state_root_path) == False:
                os.makedirs(self.state_root_path)
            self.state["_dynamic_state"] = self.dstate.export()
            state_path = os.path.join(self.state_root_path,self.__class__.__name__)
            with open(state_path,'w') as f:
                try:
                    json.dump(self.state,f, indent=4)
                except BaseException as e:
                    if self.debug_modules:
                        raise e
                    self.print_error(e)

    

    #@__trackruntime("handle_log")
    def handle_check(self, row, reader):

        if self.enabled == False:
            return
        if reader not in self.readers:
            return
        try:
            self.check(row)
            self.check_count += 1
        except BaseException as e:
            if self.debug_modules:
                raise e
            traceback.print_tb(e.__traceback__)
            self.print_error(e)
            self.enabled = False


    def handle_complete(self):
        if self.enabled == False:
            return
        try:
            self.complete()
        except AttributeError:
            pass
        except BaseException as e:
            if self.debug_modules:
                raise e
            self.print_error(e)
            self.enabled = False
            #raise e

    def handle_daily(self):
        if self.enabled == False:
            return
        try:
            self.daily()
        except AttributeError:
            pass
        except BaseException as e:
            if self.debug_modules:
                raise e
            self.print_error(e)
            self.enabled = False
            #raise e
    
    def get_readers(self):
        try:
            return self.readers
        except AttributeError:
            msg = "ERROR: No readers defined in "+self.__class__.__name__
            out.say(msg); out.log(msg)
            
    def print_error(self,e):
        error_msg = "ERROR: An error, "+str(type(e))+" "+str(e)+", occured in "+self.__class__.__name__+" and it has been disabled. \n"
        error_msg += str(traceback.format_exc())
        out.send_email(config.ERRORS_FROM_ADDRESS, config.EMAIL_ERRORS_TO, "Error in: "+self.__class__.__name__, error_msg)
        print(error_msg)

    def queue_email(self, email_to, email_subject, email_body):
        if len(self.queued_emails) >= self.max_emails:
            msg = "Max queued emails reached, by "+self.__class__.__name__+", skipping"
            out.send_email(config.ERRORS_FROM_ADDRESS, config.EMAIL_ERRORS_TO, "Max queued emails: "+self.__class__.__name__, msg)
            print(msg)
            return

        if len(email_body) > self.max_email_length:
            email_body = "Email body was truncated at "+str(self.max_email_length) +" characters.\n\n"+email_body[0:self.max_email_length]
            print("Email body too long in "+self.__class__.__name__+", truncating")

        recipients = email_to
        if type(email_to) == str:
            recipients = [email_to]

        for r in recipients:
            self.queued_emails.append(
                {
                    "to"        : r,
                    "subject"   : email_subject,
                    "body"      : email_body
                }
            )

    def send_emails(self):
        if self.enabled == False:
            return
        for e in self.queued_emails:
            self.send_email(config.FROM_ADDRESS, e["to"], e["subject"], e["body"])


    def send_email(self, email_from, email_to, email_subject, email_body, bcc=None):
        if self.email_all_monitors_to and self.email_all_monitors_to not in email_to and self.force_recipient is None:
            out.send_email(email_from, self.email_all_monitors_to, email_subject, email_body, bcc)
        out.send_email(email_from, email_to, email_subject, email_body, bcc)


    def say(self,text):
        out.say(self.__class__.__name__+" "+text)

    def log(self,text):
        out.log(self.__class__.__name__+" "+text)

    def debug(self,text):
        out.debug(self.__class__.__name__+" "+text)




# Decorator example, for future reference
def monitorcheck(func):
    def wrapper_monitorcheck(*args, **kwargs):
        # load state data
        print("before")
        value = func(*args, **kwargs)
        print("after")
        return value
        # save state data

    return wrapper_monitorcheck