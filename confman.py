'''
confman is the configuration management wrapper around pyratemp written
by John Yi.

pyratemp and yaml2pyratemp were written by Roland Koebler

'''

import os
import platform
import re
import site
import sys
import string
import subprocess
import time

# adding pythonpath to point to server module python library (very limited 2.4.4)
# use the guard statements to select what I hope will just be either windows.
# (Hoping that it will be that easy.)
if re.search('(?i)linux',platform.platform()):
    sys.path.append('/opt/opsware/smopylibs2')
    site.addsitedir('/opt/opsware/sm/config.deployment/pyratemp/yaml.2.4.4.zip')
elif re.search('(?i)window',platform.platform()):
    smopython2 = 'C:\\Program Files\\Opsware\\smopython2'
    sys.path.append('C:\\Program Files\\Opsware\\agent\\pylibs')
    sys.path.append('C:\\Program Files\\Opsware\\smopylibs2')
    site.addsitedir('C:\\Program Files\\Opsware\\sm\\config.deployment\\pyratemp\\yaml.2.4.4.zip')
    smopy2dir = [ dir for dir in os.listdir(smopython2) if os.path.isdir(os.path.join(smopython2,dir)) ][-1:][0]
    site.addsitedir(os.path.join('C:\\Program Files\\Opsware\\smopython2',smopy2dir,'Lib\\site-packages'))
else:
    sys.path.append('/opt/opsware/smopylibs2')

#
# Define exception
#
from pytwist.com.opsware.custattr import NoSuchFieldException

class NoSuchHWFieldException(Exception):
    pass

class NoCustomAttributeException(Exception):
    pass

class TemplateParseError(Exception):
    pass

class TemplateSyntaxError(Exception):
    pass

class TemplateRenderError(Exception):
    pass

class NoDatasetException(Exception):
    pass

class NoTemplateException(Exception):
    pass

class ImproperlyNamedCAException(Exception):
    pass

#
# Helper methods.
#
def fileWriter(filePath,fileContents):
    try:
        directory,filename = os.path.split(filePath)
        if not os.path.exists(directory):
            os.makedirs(directory)
        of = file(filePath,'w')
        of.write(fileContents)
        of.close()
    except IOError,args:
        of.close()
        raise IOError,args
    except UnicodeEncodeError,args:
        of.close()
        raise UnicodeEncodeError,args
    except OSError,args:
        raise OSError,directory

def fileReader(filePath):
        try:
            of = open(filePath,'r')
        except IOError,args:
            raise IOError,args
        datasetString = of.read()
        of.close()
        return datasetString

def load_data(datasetString):
    """
    Load data from data-files using either 'yaml' or 'simplejson'.
   
    Exits if data is invalid or neither 'yaml' nor 'simplejson' are found.

    :Parameters:
        - dataset: dataset with an extension, either .json or .yaml
    :Returns: read data (dict)
    """
    dataset = None

    try:
        import simplejson
        import pyratemp
        #
        # loading data from JSON. If this fails it will attempt to load it
        # as YAML.
        #
        dataset = pyratemp.dictkeyclean(simplejson.loads(datasetString))
    except ImportError:
        sys.stderr.write("ERROR: python-module 'simplejson' not found.\n")
        sys.exit(4)
    except ValueError:
        try:
            import yaml
            dataset = yaml.load(datasetString)
        except ImportError:
            sys.stderr.write("ERROR: python-module 'yaml' not found.\n")
            sys.exit(4)
        except ValueError:
            raise ValueError,"The given buffer is not valid JSON or YAML:\n%s" % datasetString
        except yaml.parser.ParserError,args:
            raise ValueError,"The given buffer is not valid JSON or YAML\n%s" % datasetString
        except yaml.scanner.ScannerError,args:
            raise ValueError,"The given buffer is not valid JSON or YAML\n%s" % datasetString
    return dataset


class Translator(object):
    def __init__(self,pattern,objref):
            self.objref = objref
            self.pattern = re.compile(pattern,re.X)
    def sub(self,text):
            return self.pattern.sub(self.__repl,text)
    def __repl(self,matchobj):
            matchstr = matchobj.group(0)[1:-1]
            return self.getvalue(self.objref,matchstr)
    def getvalue(self,objref,name):
        raise TypeError,"getvalue needs to implemented with the following interface: def getvalue(self,objref,name) within your class."
    def tokenExists(self,text):
        if self.pattern.search(text):
            return True
        else:
            return False

#
# Within configuration management there always seem to be the same pattern:
# configuration file = dataset + template
# The classes below represent this pattern. Hopefully it'll be flexible enough
# to use whatever template engine you'd like.
#

class Configuration(object):
    def __init__(self,metadataBuffer):
        self.metadataset = Metaset(metadataBuffer)
        self.configs = None

    def deployConfigs(self):
        self.generateConfigs()
        self.writeConfigs()
        self.setPermissionConfigs()
        self.setOwnerGroupConfigs()

    def writeConfigs(self):
        pass
    def readConfigs(self):
        pass
    def generateConfigs(self):
        pass

    def executeCommands(self):
        for cmd in self.metadataset.getCommands():
            subprocess.call("%s" % cmd,shell=True)
    
    def setPermissionConfigs(self):
        for (filepath,fileobj) in self.configs.iteritems():
            if re.match('(?i)linux',platform.platform()):
                if fileobj.has_key('perms'):
                    subprocess.call("/bin/chmod %s %s" % (fileobj['perms'],filepath),shell=True)
            else:
                # for windows permissioning, but not implemented yet.
                pass
        
    def setOwnerGroupConfigs(self):
        for (filepath,fileobj) in self.configs.iteritems():
            if re.match('(?i)linux',platform.platform()):
                if fileobj.has_key('og'):
                    subprocess.call("/bin/chown %s %s" % (fileobj['og'],filepath),shell=True)
            else:
                # for windows permissioning, but not implemented yet.
                pass

    def writeSignature(self):

        '''
        Will probably implement a hook method for all the classes that inhert for
        this functionality.
        '''
        pass
    
    def verifySignature(self):
        '''
        Will probably implement a hook method for all the classes that inhert for
        this functionality.
        '''
        pass


class SAConfiguration(Configuration):
    '''
    This class implements SA custom attributes as well as pyratemp to generate
    configurations. If you just need a pure pyratemp implementation. Use
    PyraConfiguration.
    '''
    class CAsub(Translator):
        pattern =   r"""\@   # Starting with '@'
                    (?:\w+)? # an optional object specifier
                    ((?:\.)|(\.[0-9]+\.))?  # followed by an optional '.'
                    [\w-]+      # a string
                    \@       # ending with another @
                    """
        def __init__(self,ObjRef,service='ts.server.ServerService'):
            try:
                from pytwist import twistserver
                ts = twistserver.TwistServer()
                self.service = eval(service)
            except ImportError,args:
                raise ImportError,args
            super(SAConfiguration.CAsub,self).__init__(SAConfiguration.CAsub.pattern,ObjRef)
        def getvalue(self,objref,name):
            return self.service.getCustAttr(objref,name,True)

    class HWsub(Translator):
        pattern =   r"""\!   # Starting with '!'
                    (?:\w+)? # an optional object specifier
                    ((?:\.)|(\.[0-9]+\.))?  # followed by an optional '.'
                    [\w-]+      # a string
                    \!       # ending with another !
                    """
        def __init__(self,HWDict):
            super(SAConfiguration.HWsub,self).__init__(SAConfiguration.HWsub.pattern,HWDict)
        def getvalue(self,objref,name):
            if re.match('^ipaddress(_[0-9])*$',name):    
                if re.match('^ipaddress_[0-9]$',name):
                    (ipaddress,interface) = string.split(name,'_')
                    return self.objref['interfaces'][int("%s" % interface)]['ip_address']
                else:
                    #
                    # Initialize servervo to get server specific information
                    #
                    from pytwist import twistserver
                    from pytwist.com.opsware.server import ServerRef
                    ts = twistserver.TwistServer()
                    serverref = ServerRef(self.objref['mid'])
                    servervo = ts.server.ServerService.getServerVO(serverref)
                    return servervo.primaryIP
            elif re.match('^nodename$',name):
                return self.objref['system_name']
            elif re.match('^nodenum$',name):
                return re.match('([A-Za-z]+)([0-9]+)([A-Za-z])+',string.split(self.objref['system_name'],'-')[0]).group(2)
            elif re.match('^gateway$',name):
                return self.objref['default_gw']
            elif re.match('^netmask(_[0-9])*$',name):
                if re.match('^netmask_[0-9]$',name):
                    (netmask,interface) = string.split(name,'_')
                else:
                    ipaddress = name
                    interface = 0
                return self.objref['interfaces'][int("%s" % interface)]['netmask']
            elif re.match('^macaddress(_[0-9])*$',name):
                if re.match('^macaddress_[0-9]$',name):
                    (macaddress,interface) = string.split(name,'_')
                else:
                    macaddress = name
                    interface = 0
                return self.objref['interfaces'][int("%s" % interface)]['hw_addr']
            elif re.match('^dnsservers$',name):
                import simplejson
                return simplejson.dumps([ element for element in self.objref['device_dns_servers'] ])
            elif re.match('^domains$',name):
                import simplejson
                return simplejson.dumps([ element for element in self.objref['device_dns_search_domains'] ])
            elif re.match('^hw$',name):
                import simplejson
                return simplejson.dumps(self.objref)
            else:
                raise NoSuchHWFieldException,name

    def __init__(self,configName,ObjRef,HWDict={},service='ts.server.ServerService'):
        try:
            from pytwist import twistserver
            ts = twistserver.TwistServer()
            self.service = eval(service)
            self.casub = self.CAsub(ObjRef)
            self.hwsub = self.HWsub(HWDict)
            self.objref = ObjRef
            if not re.match("^(\w+\.)+metaconf$",configName): # The configuration needs to have a metaconf extension.
                raise ImproperlyNamedCAException,"Configuration custom attribute needs to have <ca name>.metaconf extension."
            metadataBuffer = self.service.getCustAttr(ObjRef,configName,True)
            metadataBuffer = self.hwsub.sub(self.casub.sub(metadataBuffer))
            #metadataBuffer = self.casub.sub(metadataBuffer)
            #metadataBuffer = self.hwsub.sub(metadataBuffer)
        except ImportError,args:
            raise ImportError,args
        except NoSuchFieldException,args:
            raise NoCustomAttributeException,args
        super(SAConfiguration,self).__init__(metadataBuffer)
    
    def _searchAndReplace(self,text,level=1):
        text = self.hwsub.sub(self.casub.sub(text))
        if self.casub.tokenExists(text) and not level >= 6:
            level = level + 1
            text = self._searchAndReplace(text,level)
        return text
        
    def writeConfigs(self):
        try:
            for (filepath,fileobj) in self.configs.iteritems():
                fileWriter(filepath,fileobj['filecontent'])
                stat = os.lstat(filepath)
                if (int(time.time()) - stat[8]) < 60:
                    print "Wrote file: %s" % filepath
                else:
                    print "Doesn't look like file %s was updated." % filepath
        except IOError,args:
            print "%s" % args
            raise IOError,args

    def generateConfigs(self):
        '''
        This assumes that a file for the template and dataset exists.
        '''
        configFiles = {}
        try:
            import pyratemp
            for config in self.metadataset.getConfigs():
                if config.has_key('dataset'):
                    if not re.match("^(\w+\.)+(json|yaml)$",config['dataset']): # The configuration needs to have a metaconf extension.
                        raise ImproperlyNamedCAException,"Dataset needs to have a <ca dataset>.json or <ca dataset>.yaml extension."
                    datasetBuffer = self.service.getCustAttr(self.objref,config['dataset'],True)
                elif config.has_key('datasetFile'):
                    datasetBuffer = fileReader(config['datasetFile'])
                else:
                    raise NoDatasetException,"Please specify a dataset with either a dataset or datasetFile json key."
                #datasetBuffer = self.casub.sub(fileReader(config['datasetFile']))
                #datasetBuffer = self.casub.sub(datasetBuffer)
                #datasetBuffer = self.hwsub.sub(datasetBuffer)
                datasetBuffer = self._searchAndReplace(datasetBuffer)
                #if not self.casub.tokenExists(config['dataset']):
                #    raise MissingDatasetCA,"Specify @%s@ instead of %s in dataset field." % (config['dataset'],config['dataset'])
                #datasetBuffer = config['dataset']
                dataset = load_data(datasetBuffer)
                #print "config['dataset']: %s" % config['dataset']
                #dataset = load_data(self._searchAndReplace(config['dataset']))
                #pytemp = pyratemp.Template(fileReader(config['templateFile']))
                if config.has_key('template'):
                    if not re.match("^(\w+\.)+template$",config['template']): # The configuration needs to have a metaconf extension.
                        raise ImproperlyNamedCAException,"Dataset needs to have a <ca template>.template extension."
                    pytemp = pyratemp.Template(self.service.getCustAttr(self.objref,config['template'],True))
                elif config.has_key('templateFile'):
                    pytemp = pyratemp.Template(fileReader(config['templateFile']))
                else:
                    raise NoTemplateException,"Please specify a template with either a template or templateFile json key."
                #if not self.casub.tokenExists(config['template']):
                #    raise MissingTemplateCA,"Specify @%s@ instead of %s in template field." % (config['template'],config['template'])
                #pytemp = pyratemp.Template(self.casub.sub(config['template']))
                # initialize dictionary with filecontents.
                configFiles[config['configFile']] = {'filecontent' : pytemp(**dataset).encode("utf-8")}
                if config.has_key('perms'):
                    configFiles[config['configFile']]['perms'] = config['perms']
                if config.has_key('og'):
                    configFiles[config['configFile']]['og'] = config['og']
        except ImportError,args:
            raise ImportError,args
        except IOError,args:
            raise IOError,args
        except NoSuchFieldException,args:
            raise NoCustomAttributeException,args
        except pyratemp.TemplateSyntaxError, err:
            raise TemplateSyntaxError,err
        except pyratemp.TemplateRenderError,err:
            raise TemplateRenderError,err
        except pyratemp.TemplateParseError,err:
            raise TemplateParseError,err
        self.configs = configFiles


class PyraConfiguration(Configuration):
    '''
    This class implements a purely pyratemp approach to configuration. 
    It reads template and dataset files to generate a configuration.
    '''

    def __init__(self,metaFile):
        try:
            super(PyraConfiguration,self).__init__(fileReader(metaFile))
        except IOError,args:
            raise IOError,args

    def generateConfigs(self):
        '''
        This assumes that a file for the template and dataset exists.
        '''
        configFiles = {}
        try:
            import pyratemp
            for config in metadataset.getConfigs():
                dataset = metadataset.getDatasetDict(fileReader(config['datasetFile']))
                pytemp = pyratemp.Template(fileReader(config['templateFile']))
                configFiles[config['configFile']] = pytemp(**dataset).encode("utf-8")
        except ImportError,args:
            raise ImportError,args
        except IOError,args:
            raise IOError,args
        return configFiles


class Dataset(object):
    '''
        Dataset accepts a string that represents a JSON or YAML File.
    '''

    def __init__(self,datasetString,storePathDir=None):
        #
        # Would like this to be protected varibles, but not sure how to
        # do this within Python
        #
        self._dataformat = None
        self._datasetString = datasetString
        self._datasetDict = load_data(datasetString)


    def writeDatasetFile(self,datasetFilePath,format='json'):
        if format == 'json':
            try:
                import simplejson    
                datasetBuffer = simplejson.dumps(self._datasetDict,sort_keys=True, indent=2)
                fileWriter(datasetFilePath,datasetBuffer)
            except ImportError,args:
                raise ImportError,args
            except IOError,args:
                raise IOError,args
        elif format == 'yaml':
            try:
                import yaml
                datasetBuffer = yaml.dump(self._datasetDict,default_flow_style=False)
                fileWriter(datsetFilePath,datasetBuffer)
            except ImportError,args:
                raise ImportError,args
            except IOError,args:
                raise IOError,args
        else:
            raise NotImplmentedError,"format='json' or format='yaml' needs to be implemented"

    def readDatasetFile(self,datasetFile):
        pass    
    def getDatasetDict(self):
        return self._datasetDict


class Metaset(Dataset):
    
    '''
        Metaset(<yaml or json formatted buffer>)
        It then loads
        metadata for the configuration and the dataset for the configuration files
        to be generated. The format for this metadata is set in this class. Any changes
        to that format should be done here.
    '''

    def getName(self):
        return self._datasetDict['name']
    def getConfigs(self):
        return self._datasetDict['configs']
    def getCommands(self):
        if self._datasetDict.has_key('execute'):
            return [ cmd for cmd in self._datasetDict['execute'] if cmd ]
        else:
            return []


class Template(object):
    def __init__(self,name):
        pass
    def readTemplateFile(self):
        pass
    def writeTemplateFile(self):
        pass
    def getTemplateFilePath(self):
        pass

    
    