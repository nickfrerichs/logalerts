
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
import glob
import importlib
import sqlite3

class Logmonitor:

    # These class variables, shared by all objects. Put instance variables in __init__
    state_root_path = config.STATE_ROOT_PATH
    mail_server = config.MAILSERVER

    max_emails = 100
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

        self.enabled = True    
        self.cfg = {}
        self.load_file_configs()
        self.runtimes = {}

        self.state = {}
        self.dstate = None
        self.sqlstate = SQLState(os.path.join(self.state_root_path,self.__class__.__name__+".sqlite"))
        self.queued_emails = list()
        self.__load_state()
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
                "_dynamic_state" : {},
                "mail_queue" : []
            }

        if self.state.get("_dynamic_state") is None:
            self.dstate = dynamicstate.DynamicState({})

        else:
            self.dstate = dynamicstate.DynamicState(self.state["_dynamic_state"])
            # Don't save this twice in memory, it can be fairly large
            del(self.state["_dynamic_state"])


        if self.state.get("mail_queue") is None:
            self.state["mail_queue"] = []

        # Add any queued emails that were sent to disk
        for e in self.state["mail_queue"]:
            self.queue_email(e["to"],e["subject"],e["body"])
        self.state["mail_queue"] = []

    def load_file_configs(self):
        # self.cfg_file: Check for and load config from dedicated file first
        cfg_name = "config_"+self.__class__.__name__
        cfg_filename = os.path.join(os.path.dirname(__file__),"../logmonitors/config_file", cfg_name+".py")
        if os.path.exists(cfg_filename):
            try:
                spec = importlib.util.spec_from_file_location(cfg_name,cfg_filename)
                self.cfg_file = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(self.cfg_file)
                self.say("loaded cfg_file: "+cfg_name+".py",2)
            except BaseException as e:
                if self.debug_modules:
                    raise e
                else:
                    self.say("ERROR loading "+cfg_filename+ ' enable debug_modules to see more')
                self.enabled = False

        # self.cfg_json: Check for and load from 
        json_name = "config_"+self.__class__.__name__+".json"
        json_filename = os.path.join(os.path.dirname(__file__), "../logmonitors/config_json", json_name)
        if os.path.exists(json_filename):
            try:
                with open(json_filename) as f:
                    self.cfg_json = json.load(f)
                    self.say("loaded cfg_json: "+json_name,2)
            except BaseException as e:
                if 1==0 and self.debug_modules:
                    raise e
                else:
                    self.say("ERROR loading "+json_name+' enable debug_modules to see more')
                self.enabled = False



    def load_config(self, cfg):
        # self.cfg: Also load from main config file
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
            # Don't save this twice in memory, it can be fairly large
            del(self.state["_dynamic_state"])

            if self.sqlstate.db is not None:
                self.sqlstate.close()
                out.say("DB Closed "+self.__class__.__name__,2)


    

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
            self.say(msg); self.log(msg)
            
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
            success = self.send_email(config.FROM_ADDRESS, e["to"], e["subject"], e["body"])
    
           # print(result)
            if success == False and len(self.state["mail_queue"]) <= self.max_emails:

                self.state["mail_queue"].append({
                    "to"        : e["to"],
                    "subject"   : e["subject"],
                    "body"      : e["body"]
                })


    def send_email(self, email_from, email_to, email_subject, email_body, bcc=None):
        success = False
        if self.email_all_monitors_to and self.email_all_monitors_to not in email_to and self.force_recipient is None:
            self.log("Sent email to "+self.email_all_monitors_to +' (email_all_monitors_to), "'+email_subject+'"')
            out.send_email(email_from, self.email_all_monitors_to, email_subject, email_body, bcc)
        success = out.send_email(email_from, email_to, email_subject, email_body, bcc)
        if success == True:
            self.log("Sent email to "+email_to+', "'+email_subject+'"')
        return success


    def say(self,text,verbose=0):
        out.say(self.__class__.__name__+" "+text,verbose)

    def log(self,text):
        out.log(self.__class__.__name__+" "+text)

    def debug(self,text):
        out.debug(self.__class__.__name__+" "+text)


class SQLState:

    def __init__(self, path):
        self.db = None
        self.cur = None
        self.db_path = path
        self.expires = {}

    # Ensure database is loaded, initialize a table (basically create it if it doesn't exist)
    def init_table(self, table_name, schema, expire=0):
        if self.db == None:
            self.__load_sqlstate()

        # Ensure table exists with expire column for when the data should be purged
        self.cur.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='%s'" % (table_name))
        if self.cur.fetchone()[0] < 1:        
            self.cur.execute("CREATE TABLE "+table_name+" ("+schema+", logalerts_expire integer)")
            self.cur.execute("INSERT INTO logalerts_expire VALUES (?,?)", (table_name,expire))
            self.db.commit()

        # Add the expire value to the dictionary so it can be easily used later
        self.cur.execute("SELECT table_name, expire FROM logalerts_expire WHERE table_name = ?", (table_name,))
        row = self.cur.fetchone()
        self.expires[row[0]] = row[1]


        # Purge all data older than the expire time
        self.cur.execute("DELETE FROM "+table_name+" WHERE logalerts_expire != 0 AND logalerts_expire < ?",(int(time.time()),))
        # print("Purged rows: "+str(self.cur.rowcount))
        self.db.commit()

    def insert_values(self, table_name, values):

        if self.expires[table_name] == 0:
            values.append(0)
        else:
            values.append(int(time.time())+self.expires[table_name])

        cols = ""
        for i in range(1,len(values)):
            cols += "?,"
        cols += "?"
        self.cur.execute("insert into "+table_name+" values ("+cols+")",values)

    def __load_sqlstate(self):
        self.db = sqlite3.connect(self.db_path)
        self.cur = self.db.cursor()

        # If new, create table to track expire times for other future tables
        self.cur.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='logalerts_expire'")
        if self.cur.fetchone()[0] < 1:        
            self.cur.execute("CREATE TABLE logalerts_expire (table_name text, expire integer)")
            self.db.commit()


    def __save_sqlstate(self):
        self.db.commit()
        self.db.close()

    def close(self):
        self.__save_sqlstate()

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