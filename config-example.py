STATE_ROOT_PATH = ""
TEMP_ROOT_PATH = ""
STATE_FILE = ""
DAILY_RUN_HOUR = 3
DAEMON_INTERVAL = 30

SYSLOG_HUP_CMD = "/usr/bin/systemctl kill -s HUP rsyslog.service"

MAILSERVER = ""
FROM_ADDRESS = ""
ERRORS_FROM_ADDRESS = ""
EMAIL_ERRORS_TO = ""

# For testing
COPY_INSTEAD_OF_MOVE = False
PRINT_EMAILS_INSTEAD_OF_SEND = False
DEBUG_MODULES = False
# FORCE_RECIPIENT = ""
# EMAIL_ALL_MONITORS_TO = ""

RUNLOG_PATH = ""
DEBUGLOG_PATH = ""
ERRORLOG_PATH = ""

# You must fill out enabled monitors and readers. Config is optional, or supply empty dict
ENABLED_MONITORS = {
#    "monitor_dc_brute_force_logins" : {
#        "email_to"  :   "alertme@domain.com"
#    },
#    "monitor_dc_kerberos_scanning"      : {
#        "email_to"  :   "alertme@domain.com"
#    }
}

# Use this to only enable readers, if empty or missing, no readers are enabled
ENABLED_READERS = {
#    "reader_dclogs"         : {
#        "files" : ["/var/log/user.log"]
#    }
}


# Set these to be alerted by watchdog when disk usage in a directory is too high, in bytes
DISK_USAGE_LIMITS = {
  #  "/var/log"  :   (1024 * 1024 * 600)
}
