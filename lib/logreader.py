import os,sys
import traceback
import shutil
import json
import time
import datetime
import glob
import hashlib
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import config
import output as out


class Logreader:
    state_root_path = config.STATE_ROOT_PATH

    def __init__(self):
        try:
            self.debug_modules = config.DEBUG_MODULES
        except AttributeError:
            self.debug_modules = False

        self.cfg = {}
        self.enabled = True
        self.state = {}
        self.__load_state()

        try:
            self.EMAIL_ERRORS_TO = config.ENABLED_READERS[self.__class__.__name__]["email_errors_to"]
        except (AttributeError, KeyError):
            self.EMAIL_ERRORS_TO = config.EMAIL_ERRORS_TO

        # Could check that everything is defined and print errors / disable the reader up front

    def load_config(self, cfg):
        self.cfg = cfg

    def __load_state(self):
        state_path = os.path.join(self.state_root_path,self.__class__.__name__)
        try:
            with open(state_path) as f:
                self.state = json.load(f)
        except FileNotFoundError:
            self.state = {
                "reader_name" : self.__class__.__name__,
                "last_read_count" : 0,
                "last_read_timestamp" : 0,
                "last_error_count" : 0,
                "last_none_count"  : 0,
                "missed_read_watchdogs" : 0,
                "missed_none_watchdogs" : 0
            }

    def save_state(self):
        if self.enabled:
            if os.path.exists(self.state_root_path) == False:
                os.makedirs(self.state_root_path)
            state_path = os.path.join(self.state_root_path,self.__class__.__name__)
            with open(state_path,'w') as f:
                try:
                    json.dump(self.state,f, indent=4)
                except BaseException as e:
                    if self.debug_modules:
                        raise e
                    self.print_error(e)


    def print_error(self,e):
        error_msg = "ERROR: An error, "+str(type(e))+" "+str(e)+", occured in "+self.__class__.__name__+"\n"
        error_msg += str(traceback.format_exc())
        out.send_email(self.ERRORS_FROM_ADDRESS, self.EMAIL_ERRORS_TO, "Error in: "+self.__class__.__name__, error_msg)
        print(error_msg)


class Filereader(Logreader):

    temp_log_root = config.TEMP_ROOT_PATH
    initialized_log_files = []

    def __init__(self):
        super().__init__()
        self.temp_files = []
        self.runtimes = {}
        self.read_count = 0
        self.none_count = 0
        self.current_timestamp = int(time.time())
        self.current_datetime = datetime.datetime.today()
        self.errors = []
        
        try:
            self.copy_instead_of_move = config.COPY_INSTEAD_OF_MOVE
        except AttributeError:
            self.copy_instead_of_move = False

        
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

    def initialize(self):
        
        if self.state["last_error_count"] > 1000:
            self.enabled = False
            msg = "Too many errors on last run: "+str(self.state["last_error_count"])
            out.send_email(self.ERRORS_FROM_ADDRESS, self.EMAIL_ERRORS_TO, "Reader disabled: "+self.__class__.__name__,msg)
            return

        log_files = self.cfg["files"]
        if log_files == None:
            out.say("Reader disabled: -> "+self.__class__.__name__+" <- no logfiles defined in config")
            self.enabled = False
            return

        # If I decide to use glob.glob, could concat results together so that readers could share those
        for log_file in log_files:
            
            temp_file = self.__get_temp_filepath(log_file)
            # Check if another reader already initialized this file
            if temp_file in self.initialized_log_files:
                self.temp_files.append(temp_file)
                continue
            if os.path.isfile(log_file) == False:
                print("Skipping, file doesn't exist: "+log_file)
                continue

            # Check if temp_file already exists, then decide if it should be renamed and processed as well? Could be left over from an error
            if os.path.isfile(temp_file):
                extra_file = temp_file+"_"+str(self.current_timestamp)
                shutil.move(temp_file,extra_file)
                self.temp_files.append(extra_file)
                print("Existing log file was found by "+self.__class__.__name__+", it will also be scanned: "+extra_file)

            # Check for old temp files
            for extra_file in glob.glob(temp_file+"_*"):
                print("Existing log file was found by "+self.__class__.__name__+", it will also be scanned: "+extra_file)
                self.temp_files.append(extra_file)

            if self.copy_instead_of_move:
                shutil.copy(log_file, temp_file)
            else:
                shutil.move(log_file, temp_file)
            self.temp_files.append(temp_file)

            # Store in global list so other readers can share the file
            self.initialized_log_files.append(temp_file)
            

    def read(self):
        for log_file in self.temp_files:
            with open(log_file, errors="replace") as f:
                for line in f:
                    if line != None:
                        try:
                            new_row = self.json_row(line.strip())
                            if new_row is None:
                                self.none_count += 1
                                continue
                            new_row["logreader_name"] = self.__class__.__name__
                            yield new_row
                            self.read_count += 1
                        except BaseException as e:
                            if self.debug_modules:
                                raise(e)
                            msg = "ERROR in "+self.__class__.__name__+" reading line: "+line+"\n"
                            msg += str(traceback.format_exc())
                            self.errors.append(msg)

                            # Over 100MB of error text, time to disable
                            if sys.getsizeof(self.errors) > 104857600:
                                msg = "Too many errors current run: "+str(len(self.errors))
                                out.send_email(config.ERRORS_FROM_ADDRESS, self.EMAIL_ERRORS_TO, "Reader disabled: "+self.__class__.__name__, msg)
                                self.enabled = False
                                return
                            
                            continue
                    else:
                        continue


        self.state["last_read_count"] = self.read_count
        self.state["last_none_count"] = self.none_count
        self.state["last_error_count"] = len(self.errors)
        if self.read_count > 0:
            self.state["last_read_timestamp"] = int(time.time())
                

    # Called once monitors are all done processing. Delete the read log files
    def cleanup(self):

        for log_file in self.temp_files:
            try:
                os.remove(log_file)
            except FileNotFoundError:
                pass
        
        if len(self.errors) > 0:
        # Log any read errors
            for line in self.errors:
                out.error(line)

        # Email errors encountered while reading
        
            if len(self.errors) >= 25:
                email_errors = [self.__class__.__name__+" - too many errors "+str(len(self.errors)-25)+" truncated."]
                email_errors += self.errors[0:25]
            else:
                email_errors = self.errors

            out.send_email(config.ERRORS_FROM_ADDRESS, self.EMAIL_ERRORS_TO, "Reader errors: "+self.__class__.__name__, "\n".join(email_errors))

        try:
            # This logic is annoying and duplicated, anymore and it should be re-written using variables or classes
            if self.watchdog.get("min_read_count") and self.read_count < self.watchdog["min_read_count"]:
                self.state["missed_read_watchdogs"] += 1
                if self.state["missed_read_watchdogs"] > self.watchdog["min_read_runs_allowed"]:
                    msg = "Reader "+self.__class__.__name__+" has read less than "+str(self.watchdog["min_read_count"]) + " matching lines "+str(self.state["missed_read_watchdogs"])+" times."
                    out.send_email(config.ERRORS_FROM_ADDRESS, self.EMAIL_ERRORS_TO, "Reader watchdog notice: "+self.__class__.__name__, msg)
            else:
                self.state["missed_read_watchdogs"] = 0

            if self.watchdog.get("min_none_count") and self.none_count < self.watchdog["min_none_count"]:
                self.state["missed_none_watchdogs"] += 1
                if self.state["missed_none_watchdogs"] > self.watchdog["min_none_runs_allowed"]:
                    msg = "Reader "+self.__class__.__name__+" has read less than "+str(self.watchdog["min_none_count"]) + " \"None\" lines "+str(self.state["missed_none_watchdogs"])+" times."
                    out.send_email(config.ERRORS_FROM_ADDRESS, self.EMAIL_ERRORS_TO, "Reader watchdog notice: "+self.__class__.__name__, msg)
            else:
                self.state["missed_none_watchdogs"] = 0



        except AttributeError:
            pass
        except BaseException as e:
            if self.debug_modules:
                raise(e)
            print(traceback.format_exc())

    def __get_temp_filepath(self,org_filepath):
        return os.path.join(self.temp_log_root,hashlib.md5(org_filepath.encode()).hexdigest())

    def say(self,text):
        out.say(text)

    def log(self,text):
        out.log(text)

    def debug(self,text):
        out.debug(text)

