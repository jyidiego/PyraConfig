'''
confgen is the command line interface to the configuration generator written by
John Yi.

pyratemp and yaml2pyratemp were written by Roland Koebler
'''


import os
import optparse
import platform
import re
import site
import sys
import string

#
# adding pythonpath here to pytwist,coglib etc.
#
if re.search('(?i)linux',platform.platform()):
    sys.path.append('/opt/opsware/smopylibs2')
    import simplejson
    import bs_hardware
elif re.search('(?i)window',platform.platform()):
    smopython2 = 'C:\\Program Files\\Opsware\\smopython2'
    sys.path.append('C:\\Program Files\\Opsware\\agent\\pylibs')
    sys.path.append('C:\\Program Files\\Opsware\\smopylibs2')
    site.addsitedir('C:\\Program Files\\Opsware\\sm\\config.deployment\\pyratemp\\yaml.2.4.4.zip')
    smopy2dir = [ dir for dir in os.listdir(smopython2) if os.path.isdir(os.path.join(smopython2,dir)) ][-1:][0]
    site.addsitedir(os.path.join('C:\\Program Files\\Opsware\\smopython2',smopy2dir,'Lib\\site-packages'))
    import simplejson
    from cog import bs_hardware
else:
    sys.path.append('/opt/opsware/smopylibs2')

global version
version = '1.5.4'

from pytwist import twistserver
from pytwist.com.opsware.server import ServerRef
from pytwist.com.opsware.common import NotFoundException
from pytwist.com.opsware.custattr import NoSuchFieldException
from confman import NoCustomAttributeException
from confman import NoSuchHWFieldException
from confman import TemplateRenderError
from confman import TemplateSyntaxError
from confman import NoDatasetException
from confman import NoTemplateException
from confman import ImproperlyNamedCAException
from confman import SAConfiguration
from coglib import hashers

def main():
    # initialize
    p = optparse.OptionParser(  version=version,\
                                description="This a driver interface for pyratemp configuration management. Version: %s" % version,\
                                conflict_handler="resolve"  )
    p.add_option('--ca', help="custom attribute name that has the meta configuration info.")
    (options,arguments) = p.parse_args()
    #ts = twistserver.TwistServer()
    #ServerService = ts.server.ServerService
    if options.ca:
        print "retrieving hardware dictionary...."
        hw = bs_hardware.construct_device_dictionary()
        sref = ServerRef(hw['mid'])
        sa = SAConfiguration(options.ca,sref,hw,service='ts.server.ServerService')
        action = ['genconfig','runcmds']
        if arguments:
            if re.match('(?i)genconfig',arguments[0]):
                print "\ndeploying configurations..."
                sa.deployConfigs()
                #print "\nrunning commands..."
                #sa.executeCommands() # by default if you generate configs
                #                     # you'll also execute any post cmds.
            elif re.match('(?i)runcmds',arguments[0]):
                sa.executeCommands()
        else:
            p.print_help()
            print "Please provide an action: %s" % action
    else:
        p.print_help()




if __name__ == '__main__':
    try:
        main()
    except IOError,args:
        print "Unable to open or read a file: %s" % args
        sys.exit(1)
    except OSError,args:
        print "Unable to write or read a file: %s" % args
        sys.exit(2)
    except NoCustomAttributeException,args:
        print "Custom Attribute: %s is not defined." % string.split(args.args[0].message,":")[1].strip()
        sys.exit(3)
    except NoSuchHWFieldException,args:
        print "HW Attribute: %s is not defined." % args
        sys.exit(4)
    except TemplateRenderError,args:
        print "Template Rendering encountered the following: %s" % args
        print "Most likely there is something wrong with your template."
        print "1. Make sure you closed all tags and don't forget the !, (i.e. <!--(for i in [1,2,3,4,5])--> @!i!@ <!--(end)-->)"
        print "2. Make sure that your variables are referenced somewhere either in the dataset or your tag blocks"
        print "   (i.e. The tag blocks are the stuff between <!--()-->)"
        print "3. Finally check http://www.simple-is-better.org/template/pyratemp.html"
        sys.exit(5)
    except ValueError,args:
        print "%s" % args.args[0]
        sys.exit(6)
    except NoDatasetException,args:
        print "%s" % args
        sys.exit(7)
    except NoTemplateException,args:
        print "%s" % args
        sys.exit(8)
    except ImproperlyNamedCAException,args:
        print "%s" % args
    except TemplateSyntaxError,args:
        print "Most likely you forgot to close a parenthesis. Check the syntax in your template carefully --> %s" % args
