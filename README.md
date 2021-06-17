# Logalerts
Logalerts is an adhoc framework originally created to address a need to quickly begin alerting on events contained in log files. 

The framework is intended to strike a balance between flexibility in what is required to create an alert and agility in how quickly an alert 
can be created. I created this to be able to leverage my existing Python knowledge in lieu of learning the query langauge/syntax of a more 
heavyweight, full featured log aggregation product. Writing your own python code is required to make use of the framework.

## Overview
The framework provides classes that can be used to develop your own logreaders and logmonitors.

logreaders: They read raw text files and produce a python dict of all "interesting" log entries

logmonitors: They subscribe to one or more readers and decide if and when alerts should be sent

![logalerts diagram](https://user-images.githubusercontent.com/5790350/122434244-8b8ac380-cf5c-11eb-94d1-d53038189a0a.png)

## Logreaders
How logreaders work.

## Logmonitors
How log monitors work.
