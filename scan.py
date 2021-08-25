import os,sys
if sys.version_info < (3, 0):
    sys.stdout.write("Sorry, requires Python3 (type python3 instead)\n")
    sys.exit()
import signal
import argparse
import json
import datetime
import time
import config
import subprocess
from lib.modulemanager import ReaderManager
from lib.modulemanager import MonitorManager
import lib.output as out

SIGTERM = False

STATE_FILE = config.STATE_FILE
DAILY_RUN_HOUR = config.DAILY_RUN_HOUR

RUNLOG = config.RUNLOG_PATH
DEBUGLOG = config.DEBUGLOG_PATH

DAEMON_INTERVAL = config.DAEMON_INTERVAL

state = None

def main():
    global state
    state = StateData(STATE_FILE)
    if args.run_scan:
        out.say("Starting scan",1)
        start_time = time.time()
        scan()
        run_time = int(time.time() - start_time)
        msg = "Scan completed in "+str(run_time)+" seconds"
        out.log(msg); out.say(msg,1)
        sys.exit()
    if args.daemon:
        run_daemon()


def run_daemon():
    args.verbose = max(1, args.verbose)
    next_run = 0
    out.say("Daemon starting.")
    while daemonStatus.active:
        # This allows checking for shutdown signals if between scans
        if next_run > int(time.time()):
            time.sleep(1)
            continue

        next_run = int(time.time())+DAEMON_INTERVAL
        out.say("Starting scan: "+datetime.datetime.now().isoformat())
        start_time = time.time()
        sys.stdout.flush()
        scan()
        run_time = int(time.time() - start_time)
        msg = "Scan completed in "+str(run_time)+" seconds."
        out.log(msg); out.say(msg,1)
        sys.stdout.flush()
        # Break here if inactive to make us look smarter
        if daemonStatus.active == False:
            break
        
        sleep_time = max(0,next_run - int(time.time()))
        out.say("(Next scan starts at "+str(datetime.datetime.fromtimestamp(next_run))+")\n")
        sys.stdout.flush()


def scan():
    
    out.log("Started")
    state.data["last_run_start"] = int(time.time())

    reader_manager = ReaderManager()
    monitor_manager = MonitorManager(valid_readers=reader_manager.get_active().keys())

    # First move log files and HUP rsyslog
    active_readers = reader_manager.get_active()
    for reader in active_readers:
        active_readers[reader].initialize()

    subprocess.call(config.SYSLOG_HUP_CMD, shell=True)

    # Run checks for all monitors (bulk of the work is here)
    active_readers = reader_manager.get_active()
    active_monitors = monitor_manager.get_active()
    out.say("Active readers: "+str(active_readers.keys()),1)
    out.say("Active monitors: "+str(active_monitors.keys()),1)
    for reader in active_readers:
        for row in active_readers[reader].read():
            if row is None: continue
            for monitor in active_monitors:
                active_monitors[monitor].handle_check(row, reader)

    # Call complete function on all monitors (logs are complete)
    active_monitors = monitor_manager.get_active()
    for monitor in active_monitors:
        active_monitors[monitor].handle_complete()

    # Call daily function on all monitors (in case you have a daily thing)
    if run_daily_ok() or args.force_daily:
        active_monitors = monitor_manager.get_active()
        for monitor in active_monitors:
            active_monitors[monitor].handle_daily()
        run_daily_completed()
        
    # Send all queued emails
    active_monitors = monitor_manager.get_active()
    for monitor in active_monitors:
        active_monitors[monitor].send_emails()

    # Run cleanup on all the readers (delete temp files, etc)
    active_readers = reader_manager.get_active()
    for reader in active_readers:
        active_readers[reader].cleanup()
        active_readers[reader].save_state()
        out.log(reader+" - read "+str(active_readers[reader].read_count)+" log lines.")

    # Save state data for all monitors
    for monitor in active_monitors:
        active_monitors[monitor].save_state()
        out.log(monitor+" checked "+str(active_monitors[monitor].check_count)+" lines.",1)

    state.data["last_run_complete"] = int(time.time())
    state.save()

# Logic for when to run daily things
def run_daily_ok():
    next_run = state.data["last_daily_run"] + (3600 * 24)
    if next_run <= int(time.time()) and datetime.datetime.now().hour == DAILY_RUN_HOUR:
        return True
    return False


def run_daily_completed():
    n = datetime.datetime.now()
    t = datetime.datetime(n.year,n.month,n.day,DAILY_RUN_HOUR,0,0,0)
    state.data["last_daily_run"] = int(t.timestamp())


class StateData:

    def __init__(self,file_path):
        self.file_path = file_path
        self.data = {}
        self.__load()
        self.pid_lock()

    
    def __initstate(self):
        self.data = {
            "last_daily_run" : 0,
            "last_run_complete" : 0,
            "last_run_start" : 0
        }

    def __load(self):
        try:
            with open(self.file_path) as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.__initstate()

    def save(self):
        with open(self.file_path,"w") as f:
            json.dump(self.data,f, indent=4)

    # I realize there is a race condition here, trying twice to make it less likely
    def pid_lock(self):
        for i in range(0,2):
            state_pid = self.data.get("pid")
            my_pid = os.getpid()
            if state_pid is not None:
                if state_pid == my_pid:
                    return True
                try:
                    os.kill(state_pid, 0)
                except OSError:
                    pass
                else:
                    sys.exit("Can't start, process already running.")

            self.data["pid"] = my_pid
            self.save()
            time.sleep(.2)


class DaemonStatus():
    def __init__(self):
        signal.signal(signal.SIGTERM, self.terminate)
        signal.signal(signal.SIGINT, self.terminate)
        self.active = True
        self.killtime = None

    def terminate(self, a, b):
        self.killtime = int(time.time())+60
        out.say("Finishing current scan before quitting, allowing "+str(self.gracetimeleft())+" seconds.")
        self.active = False
        
    def gracetimeleft(self):
        return int(self.killtime - time.time())

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Scan logs for alerts')
    parser.add_argument('-verbose', action="store", type=int, default=0, help='Verbose level')
    parser.add_argument('-force_daily', action="store_true", help='Force the daily functions to be called on all monitors')
    parser.add_argument('-run_scan', action="store_true", help='Run scan once, not as a daemon.')
    parser.add_argument('-daemon', action="store_true", help='Run as a daemon. (Use this with systemd)')
    args = parser.parse_args()
    config.args = args
    config.daemon = True

    if args.daemon:
        daemonStatus = DaemonStatus()

    main()