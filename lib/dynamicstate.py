import time
import json
from collections import OrderedDict

    # data_stored_in_file = {
    #     "regular item" : "permenant",
    #     "regular item2" : "also permenant",
    #     "_dynamic_state" : {
    #         "lists" : {
    #             "list1" : {
    #                 "expire" : 3600,
    #                 "data" : [
    #                         { 
    #                             "created" : 123412423,
    #                             "value"  : "nickf" 
    #                         },
    #                         {
    #                             "created" : 123412423,
    #                             "value"  : "admin-nickf"
    #                         }
    #                     ]
    #                 }
    #             }
    #         }
    #     }
    # }


        
class DynamicState:

    def __init__(self, data):
        self.dlists = {}
        self.ddicts = {}       
        if data.get("lists"):
            for dlist in data["lists"]:
                expire = data["lists"][dlist]["expire"]
                self.dlists[dlist] = DynamicList(data["lists"][dlist]["data"], expire)
        else:
            self.dlists = {}

        if data.get("dicts"):
            for ddict in data["dicts"]:
                expire = data["dicts"][ddict]["expire"]
                self.ddicts[ddict] = DynamicDict(data["dicts"][ddict]["data"], expire)
        else:
            self.ddicts = {}


    def dlist(self, name):
        return self.dlists.get(name)
    
    def init_dlist(self, name, expire=3600):
        if self.dlists.get(name) is None:
            self.dlists[name] = DynamicList([], expire)
        elif self.dlists[name].expire != expire:
            self.dlists[name].expire = expire
            self.dlists[name].purge()

    def init_ddict(self, name, expire=3600):
        if self.ddicts.get(name) is None:
            self.ddicts[name] = DynamicDict({}, expire)
        elif self.ddicts[name].expire != expire:
            self.ddicts[name].expire = expire
            self.ddicts[name].purge()

    def export(self):
        data = {
            "lists" : {},
            "dicts" : {}
        }
        for dlist in self.dlists:
            data["lists"][dlist] = {
                "data"      : self.dlists[dlist].data,
                "expire"    : self.dlists[dlist].expire
            }

        for ddict in self.ddicts:
            data["dicts"][ddict] = {
                "data"      : self.ddicts[ddict].data,
                "expire"    : self.ddicts[ddict].expire
            }

        return data

    def get(self, name):
        if self.dlists.get(name):
            return self.dlists[name]

        if self.ddicts.get(name):
            return self.ddicts[name]
    

class DynamicDict:
    # DynamicDicts are less useful than DynamicLists for various reasons. Mainly, lists are more grainular to expire,
    # so in general it's best to store data in a dlist, then sort/organize it when checking things.
    def __init__(self, data = {}, expire = 3600):
        self.expire = expire
        self.data = data
        self.session_dict = {}
        self.purge()   


    def purge(self):
        # Initialize and deleting old stuff
        old = int(time.time()) - self.expire
        newdata = {}
        newsession = {}
        for d in self.data:
            if self.data[d]["created"] < old: continue
            newdata[d] = self.data[d]
            newsession[d] = self.data[d]["value"]
        self.data = newdata
        self.session_list = newsession

    def setitem(self, key, value, created=None):
        if created is None:
            created = int(time.time())
        self.data[key] = {
                "created"   : created,
                "value"     : value
            }
        
        self.session_list[key] = value

    def get(self, key):
        return self.session_list.get(key)        


class DynamicList:

    def __init__(self, data = [], expire = 3600):
        self.expire = expire
        self.data = data
        self.session_list = []
        self.purge()        

    def purge(self):
        # Initialize and deleting old stuff
        old = int(time.time()) - self.expire
        newdata = []
        newsession = []
        for d in self.data:
            if d["created"] < old: continue
            newdata.append(d)
            newsession.append(d["value"])
        self.data = newdata
        self.session_list = newsession

    def items(self):
        return self.session_list

    def append(self, value, created=None):
        if created is None:
            created = int(time.time())
        self.data.append(
            {
                "created"   : created,
                "value"     : value
            }
        )
        self.session_list.append(value)

    def counts(self, item_key):

        item_counts = {}

        for d in self.session_list:
            if item_counts.get(d[item_key]) is None:
                item_counts[d[item_key]] = 0
            item_counts[d[item_key]] += 1

        temp = sorted(item_counts.items(), key=lambda item: item[1])
        temp.reverse()
        ordered = OrderedDict()
        for t in temp:
            ordered[t[0]] = t[1]
        return ordered


    def unique(self, key):
        items = set()
        for d in self.session_list:
            items.add(d[key])
        return list(items)

    def filter(self, key, value):
        items = list()
        for d in self.session_list:
            if d[key] == value:
                items.append(d)
        return items