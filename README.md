# Logalerts
Logalerts is an adhoc framework originally created to address a need to quickly begin alerting on events contained in log files. 

The framework is intended to strike a balance between flexibility in what is required to create an alert and agility in how quickly an alert 
can be created. I created this to be able to leverage my existing Python knowledge in lieu of learning the query langauge/syntax of a more 
heavyweight, full featured log aggregation product. Writing your own python code is required to make use of the framework.

## Overview
The framework provides classes that can be used to develop your own logreaders and logmonitors.

logreaders: They read raw text files and produce a python dict of all "interesting" log entries, logs are discarded once read. Only
new log entries are read at each scan.

logmonitors: They subscribe to one or more readers and decide if and when alerts should be sent. State (and dynamic state) data 
is made available to store information that remains available to the reader in subsequent runs. This is needed because actual log
data is discarded once read.

scan.py: The main program loops though reach log reader, then each monitor subscribed to the reader. It also manages state and
calls functions avaialble to each monitor to help send alerts and clean up as needed.

![logalerts diagram](https://user-images.githubusercontent.com/5790350/122435800-ed97f880-cf5d-11eb-9088-a862c244572a.png)

## Logreaders

Logreaders inherit the Logreader class. Class names must begin with reader_, and at minimum they must at least implement the
json_row function

```
def json_row(self, line): 
```

This function will receive a single raw log line. The reader should decide if this is a valid log line for whatever type of log
the logreader will be providing to logmonitors.

If valid, a dict should be returned containing at minimum some defaults. Though you likely want to include information that will be
useful to a logmonitor.

```
return {
    "log_host"            : "origin.hostname",
    "log_message"         : "short description of your choice",
    "log_event_timestamp" : [unix timestamp from when the even occured]

}
```

If invalid, return None to signal that nothing will be passed to logmonitors.
```
return None
```

Notes:
* There are other optional instance/object variables that can be used such as a watchdog to help alert when a reader has not been
reading any new lines for a certain time period.
* Two logreaders can (and should) be used to read the same log file(s). They essentially filter on log entries that are to be used
by logmonitors. The parent Logreader class will keep track of and only store a single copy of the log file transparently to multiple
logreaders that may be consumign the log file.
* Any lines resulting in an error are skipped and a notice of the error can be emailed. After too many errors, the reader is disabled.
* Readers have their own state data, mostly used to store stats to aid in error detection and watchdogs.



```text
class reader_demo(logreader.Filereader):

    # Optional
    watchdog = {
        "min_read_count"         : 1,
        "min_read_runs_allowed"   : 10
    }

    # Required
    def json_row(self, line):

        if "Relevent log" not in line:
            return None

        syslog_date = line [0:15]

        message = line[16:].split(" ")
        data = {
            "hostname"      : message[0],
            "ip_address"    : message[1],
            "id"            : message[2],
            "response_code" : message[3],
            "size"          : message[4]
        }


        return {
            "log_host" = f5host
            "log_message" = "CatID login data"
            "log_event_timestamp" = int(datetime.datetime.strptime(syslog_date,"%b %d %H:%M:%S %Y").timestamp())
            "data" : data
        }

logreader example
```

## Logmonitors

Logmonitors inherit the Logmonitor class. Class names must begin with monitor_, and at minimum they must contain the readers
instance variable providing a list of logreaders to subscribte to and implement the check function which is called by the main
program for each row returned by a logreader

```
    readers = [
        "reader_demo"
    ]

    def check(self, row):
```

Logmonitors do not need to do anything inside of the check function, but that is where log entries should be analized and data
stored in the inhereted state variable to be used later.

Other important functions:

```
def complete(self):
```
Called once all log entires have been read for the current run, a great place to calculate things and decide if an alert should be
sent.


```
def daily(self):
```
Called once daily at the configured daily hour. Useful for gathering data throughout a day and providing daily reports.


```
def queue_email(self, email_to, email_subject, email_body):
```
When an alert needs to be sent, use this function to add it to the queue. Emails are sent all at once at the end of the run.



Example
```
class monitor_demo(logmonitor.Logmonitor):

    readers = [
        "reader_demo"
    ]

    email_subject = "[Alert] Demo Error"

    email_body = ""

    def check(self, data):
        date_string = str(datetime.datetime.fromtimestamp(data["log_event_timestamp"]))
        self.email_body += date_string+" "+data["message"]+"\n"

    def complete(self):
        if self.email_body != "":
            self.queue_email(self.cfg["email_to"],self.email_subject,self.email_body)
```


## State data and Dynamic state data


