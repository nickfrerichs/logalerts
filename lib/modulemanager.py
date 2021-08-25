import os,sys
from collections import OrderedDict
import datetime
import logreaders
import logreaders_custom
import logmonitors
import logmonitors_custom
import output as out
import logreader
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import config

LOGMONITOR_LIBRARIES = [logmonitors, logmonitors_custom]
LOGREADER_LIBRARIES = [logreaders, logreaders_custom]

def load_module(mod_name, mod_type, cfg):
    try:
        debug_modules = config.DEBUG_MODULES
    except AttributeError:
        debug_modules = False

    mod_class = None

    if mod_name.startswith(mod_type+"_"):

        if mod_type == "monitor":
            module_objects = LOGMONITOR_LIBRARIES
        
        if mod_type == "reader":
            module_objects = LOGREADER_LIBRARIES

        module = None
        for module_object in module_objects:
            try:
                module = getattr(module_object, mod_name)
                break
            except AttributeError:
                pass

        if module == None:
            out.say(mod_type+" module "+mod_name+" not loaded: "+mod_name+".py not found.")
            return None

        try:
            mod_class = getattr(module, mod_name)()
            mod_class.load_config(cfg)
        
        except AttributeError as e:
            
            if debug_modules:
                raise e
            msg = mod_type+" module "+mod_name+" not loaded, does it contain class named "+mod_name+"?"
            out.say(msg)
            out.send_email(config.ERRORS_FROM_ADDRESS, config.EMAIL_ERRORS_TO, "Error loading " +mod_type+" "+mod_name ,msg)

            return None

        except BaseException as e:
            if debug_modules:
                raise e
            msg = mod_type+" module "+mod_name+" not loaded, ERROR: "+str(type(e))+" occured while loading."
            out.say(msg)
            out.send_email(config.ERRORS_FROM_ADDRESS, config.EMAIL_ERRORS_TO, "Error loading " +mod_type+" "+mod_name ,msg)
            
            return None
    
    return mod_class


class ModuleManager:

    def __init__(self):
        self.disabled_modules = set()
        self.loaded_modules = OrderedDict()

    def load_modules(self, modules, modules_name, enabled_list=None):
        for mod_name in dir(modules):
            if modules_name+"_" not in mod_name: continue
            if mod_name not in enabled_list.keys():
                out.say("Module not loaded: "+mod_name,2)
                continue
            module = load_module(mod_name, modules_name, enabled_list[mod_name])
            if module is not None: 
                self.loaded_modules[mod_name] = module
                if module.enabled:
                    out.say("Module loaded: "+mod_name,2)
                else:
                    out.say("Module was disabled on load: "+mod_name,1)

    def get_active(self):
        active_modules = dict()
        for mod_name in self.loaded_modules:
            if self.loaded_modules[mod_name].enabled:
                active_modules[mod_name] = self.loaded_modules[mod_name]
        return active_modules

    def get_all(self):
        return self.loaded_modules



class ReaderManager(ModuleManager):

    def __init__(self):
        super().__init__()
        try:
            self.enabled_list = config.ENABLED_READERS
        except AttributeError:
            self.enabled_list = None
        for library in LOGREADER_LIBRARIES:
            self.load_modules(library,"reader", self.enabled_list)
        logreader.Filereader.initialized_log_files = []





class MonitorManager(ModuleManager):

    def __init__(self, valid_readers=None):
        super().__init__()
        try:
            self.enabled_list = config.ENABLED_MONITORS
        except AttributeError:
            self.enabled_list = None
        for library in LOGMONITOR_LIBRARIES:
            self.load_modules(library,"monitor",self.enabled_list)

        # If readers provided, disable monitors if there are no valid readers
        if valid_readers:
            active_monitors = self.get_active()
            for module in active_monitors:
                do_enable = False
                for reader in valid_readers:
                    if reader in active_monitors[module].readers:
                        do_enable = True    
                        break
                if do_enable:
                    active_monitors[module].enabled = True
                else:
                    active_monitors[module].enabled = False
                    out.say("Module disabled: "+module+", no active readers.",2)
    


