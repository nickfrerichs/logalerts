import os,sys
import datetime
import smtplib
from email.mime.text import MIMEText
import email
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import config


def log(text, verbose=0):
    if verbose <= config.args.verbose:
        with open (config.RUNLOG_PATH,'a') as f:
            f.write(datetime.datetime.now().isoformat()+' '+text+'\n')

def debug(text):
    with open (config.DEBUGLOG_PATH,'a') as f:
        f.write(datetime.datetime.now().isoformat()+' '+text+'\n')

def say(text, verbose=0):
    if verbose <= config.args.verbose:
        print(datetime.datetime.now().isoformat()+' '+text)
        if config.daemon:
            sys.stdout.flush()

def error(text):
    with open (config.ERRORLOG_PATH,'a') as f:
        f.write(datetime.datetime.now().isoformat()+' '+text+'\n')



def send_email(email_from, email_to, email_subject, email_body, bcc=None):

    try:
        force_recipient = config.FORCE_RECIPIENT
    except AttributeError:
        force_recipient = None

    try:
        print_emails_instead_of_send = config.PRINT_EMAILS_INSTEAD_OF_SEND
    except AttributeError:
        print_emails_instead_of_send = False


    if print_emails_instead_of_send:
        say("WOULD SEND: To: %s Subject: %s" % (email_to, email_subject))
    else:

        msg = email.message.Message()
        msg.add_header('Content-Type','text')

        if force_recipient:
            msg['To'] = force_recipient
        else:
            if type(email_to) == str:
                msg['To'] = email_to
            else:
                msg['To'] = ','.join(email_to)

        msg['From'] = email_from
        msg['Subject'] = email_subject
        msg.set_payload(email_body)

        try:
            mailserver = smtplib.SMTP(config.MAILSERVER)
            mailserver.sendmail(msg['From'],msg['To'].split(","), msg.as_string())
            mailserver.quit()
            return True
        except:
            msg = "There was an error sending an email with Subject: "+email_subject
            say(msg)
            out(msg)
            return False
        


# Not sure I'll use this, but just in case
def send_email_mime(email_from, email_to, email_subject, email_body, bcc=None):

    try:
        force_recipient = config.FORCE_RECIPIENT
    except AttributeError:
        force_recipient = None

    try:
        print_emails_instead_of_send = config.PRINT_EMAILS_INSTEAD_OF_SEND
    except AttributeError:
        print_emails_instead_of_send = False


    if print_emails_instead_of_send:
        say("WOULD SEND: To: %s Subject: %s" % (email_to, email_subject))
    else:

        msg = MIMEText(email_body, "plain", "utf-8")
        msg['Subject'] = email_subject
        msg['From'] = email_from

        if force_recipient:
            recipient = force_recipient
        else:
            if type(email_to) == str:
                recipient = email_to
            else:
                recipient = ','.join(email_to)

        msg['To'] = recipient

        if bcc is not None:
            if type(bcc) == str:
                msg['Bcc'] = bcc
            else:
                msg['Bcc'] = ",".join(bcc)

        mailserver = smtplib.SMTP(config.MAILSERVER)
        mailserver.send_message(msg)
        mailserver.quit()