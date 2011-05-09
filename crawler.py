#!/usr/bin/env python

"""

- duplicates are rejected based on MD5 fingerprint
- script handles frames and "refresh" headers.

"""
import sys,os
sys.path.append(os.getcwd())

import re,Queue,string,types,hashlib,random,getopt
import urllib,urlparse
import hlsir,Image,MySQLdb
import curses
import pdb,traceback


# initialise constants and variables


savedir = "/Users/wojciechziniewicz/python/img"                        # default to current directory
fnQueue = "bc_queue.bcl"                 # list of URLs to be visited
fnVisited = "bc_visited.bcl"             # list of visited URLs
fnBackgrounds = "bc_backgrounds.bcl"     # list of urls which denied access or other error
fnNoAccess = "bc_noaccess.bcl"           # list of background graphic urls
fnMD5 = "bc_md5.bcl"                     # list of MD5 fingerprints of all downloaded graphics
fnStats = "bc_stats.bcl"                 # save statistics between sessions
fnMsg = "bc.kill"                        # semaphor file to shut down or send messages    

visited = hlsir.visited           # list of visited URLs
tmp_visited = hlsir.tmp_visited
noaccess = hlsir.noaccess           # list of urls which denied access or other error
tmp_noaccess = hlsir.tmp_noaccess
backgrounds = hlsir.backgrounds       # list of background graphic urls
tmp_backgrounds = hlsir.tmp_backgrounds
md5s = hlsir.md5s           # list of MD5 fingerprints of all downloaded graphics
tmp_md5s = hlsir.tmp_md5s
sliceX,sliceY = [hlsir.sliceX,hlsir.sliceY]
HLS_VECTOR = hlsir.HLS_VECTOR      # temporary numpy 3x3x3 array         

chrError = "!"
chrWarn = "|"
chrLoad = ">"
chrSave = "<"
chrScan = "*"
chrDupe = "@"
chrAdd  = "+"
chrMsg  = "="
chrDebug = "#"

maxVisitsBeforeSave = 3           # number of sites to visit before saving all lists and syncing to database
maxQueueSize = 1000               # maximum size to let the queue grow to
maxQueueSizeReduce = 80           # percentage to remove when queue too big
queue_cleanup_treshold  = 10

# here are some starting points if now initial URL is given.
start = [
            'http://www.randomwebsite.com/cgi-bin/random.pl',
            'http://random.yahoo.com/bin/ryl '
	   ]

# this is to track totals between sessions, but isn't implemented
stats = { 'total_kCrawled' : 0, 'total_bgBytes' : 0 }



# compile regular expressions
re_ads = re.compile(r"#|\?|/ad[-/]|/ads[^\w]|ublecl|adforc|cgi|/exec/|[-/]bin/|(amazon|netscape|microsoft|ibm|yahoo|excite)\.c|ocities.com/[^A-Z]")
re_badtypes = re.compile(r"\.(exe|zip|txt|css|ico|pdf|gif|jpg|jpeg|png|hqx|gz|z|cgi|pl|ps|map|dvi|mov|avi|mp3|wav|mid|mpg)$",re.I)
re_image = re.compile(r"""<img\s*src\s*=\s*['"](.*?)['"]\s*.*\s*>""",re.M|re.I)
re_href = re.compile(r'href\s*=\s*"(.*?)"',re.I)
re_framesrc = re.compile(r'<frame.*?src\s*=\s*"(.*?)"',re.I)
re_metarefresh = re.compile(r'URL=(.*?)"',re.I)
imagesDir = hlsir.crawler_img_library
Q = Queue.Queue(0)
cursor = hlsir.conn.cursor ()
conn   = hlsir.conn



        
def cleanupQueue():
    """Take all the items out of the Queue, put them back randomly and Uniq it"""
    global Q
    lst = []
    while not Q.empty():
        lst.append(Q.get())
    set(lst)
    while lst:
        i = random.randint(0, len(lst)-1)
        Q.put(lst[i])
        del lst[i]
        
def readMD5(msg=""):
    "read the MD5 hash filename into the given list, print optional summary at end"
    lst = []
    try:
        cursor.execute ("SELECT hash FROM visited_hashes")
        result_set = cursor.fetchall ()
        for row in result_set:
            lst.append(row)
        print "Number of visited_urls returned: %d" % cursor.rowcount 
    except MySQLdb.Error, e:
        print "An error has been passed -> %s" %e
        sys.exit (1)
    if msg: print msg % len(lst)
    return lst
    
def readLists():
    "read the Q and all the lists"
    global Q,visited,backgrounds,md5s,noaccess
    md5s =        readMD5("%s MD5 fingerprints loaded...")
    visited =     readList('visited'," %s Visited URLs loaded...")
    backgrounds = readList('backgrounds'," %s Visited background URLs loaded...")
    noaccess =    readList('noaccess'," %s URLs with no access loaded...")
    readQueue()



def prompt_user_passwd(self, host, realm):
    # to override urllib pausing for passwords
    return None, None

urllib.FancyURLopener.prompt_user_passwd = prompt_user_passwd

def readQueue():
    "read the queue table"
    global Q
    Q_temp = []
    cursor = hlsir.conn.cursor ()
    try:
        cursor.execute("""SELECT url FROM queue order by rand() LIMIT 100 """)
        Q_temp = cursor.fetchall()
        "clear queue"
        while not Q.empty():
            Q.get_nowait()
        "fill it with DB values"
        for item in Q_temp:
            Q.put(str(item)[2:-3])
    except MySQLdb.Error, e:
        print "An error has been passed -> %s" %e
        sys.exit (1)
    
def writeQueue():
    "write Queue to database"
    global Q
    cursor = hlsir.conn.cursor () 
    cursor.execute("""Delete from queue """)
    try:
        while not Q.empty():
            item = Q.get_nowait()
            query = """INSERT INTO queue (url) VALUES ('%s') """ % (item)
            cursor.execute(query)
            conn.commit()
    except MySQLdb.Error, e:
        print "An error has been passed -> %s" %e
        print "Could not insert item into DB"
    
        
def reduceQueue(p,msg=""):
    "reduce the Queue loosing a certain percentage of random strings"
    if p<1 or p>99:
        if msg: print chrError+" invalid percentage (%s%%)" % p
        return
    global Q
    fcount = 0
    Q2 = Queue.Queue(0)
    while not Q.empty():
        tmp = Q.get_nowait()
        if random.random()*100 > p:
            Q2.put(tmp)
        else:
            fcount = fcount + 1
    if msg: print msg % (fcount,p)         #
    Q = Q2
    

def filterQueue(s,msg=""):
    "filter out all strings in Queue containing the given substring"
    global Q
    fcount = 0
    Q2 = Queue.Queue(0)
    while not Q.empty():
        tmp = Q.get_nowait()
        if string.find(tmp,s)>=0:
            fcount = fcount + 1
        else:
            Q2.put(tmp)
    Q = Q2
    if msg: print msg % (fcount,s)
    return fcount

def processMsg():
    "read the kill semaphor and see if it has any instructions to follow instead of shutting down"
    global visitcount
    keepon = 0
    try:
        f = open(fnMsg,'r')
        while 1:
            l = f.readline()
            if not l: break
            if string.find(l,'filter:')==0:
                filterQueue(string.strip(l[7:]),chrMsg+" Filtered %s URLs with '%s'.")
                keepon = 1
            if string.find(l,'reduce:')==0:
                reduceQueue(string.atoi(string.strip(l[7:])),chrMsg+" Dropped %s Urls (approx %s%% of Queue).")
                keepon = 1
            if string.find(l,'save')==0:
                print "Crawled %d bytes of HTML, and %d bytes of backgrounds." % (kCrawled,bgBytes)
                syncWithDB()
                visitcount=0
                keepon = 1
            if string.find(l,'kill')==0:
                keepon = 0
        f.close()
    except IOError:
        if f: f.close()
    return keepon




def readList(message,msg=""):
    lst = []
    if message=='background':
        try:
            cursor = hlsir.conn.cursor ()
            cursor.execute ("SELECT url FROM visited_images")
            result_set = cursor.fetchall ()
            for row in result_set:
                lst.append(row)
            print "%d visited_images returned" % cursor.rowcount
        except MySQLdb.Error, e:
            print "An error has been passed -> %s" %e
            sys.exit (1)
    if message=='visited':
        try:
            cursor = hlsir.conn.cursor ()
            cursor.execute ("SELECT url FROM visited_urls")
            result_set = cursor.fetchall ()
            for row in result_set:
                lst.append(row)
            print "%d visited_urls returned" % cursor.rowcount   
        except MySQLdb.Error, e:
            print "An error has been passed -> %s" %e
            sys.exit (1)
    if message=='noaccess':
        try:
            cursor = hlsir.conn.cursor ()
            cursor.execute ("SELECT url FROM visited_noaccess")
            result_set = cursor.fetchall ()
            for row in result_set:
                lst.append(row)
            print "%d noaccess returned" % cursor.rowcount   
        except MySQLdb.Error, e:
            print "An error has been passed -> %s" %e
            sys.exit (1)
    return lst


def writeList(listtype,lst):
    if listtype=="visited":
        try:
            cursor = hlsir.conn.cursor ()
            for item in lst:
                if item:
                    query = """INSERT INTO visited_urls (url) VALUES ('%s') """ % (item)
                    """print query"""
                    cursor.execute(query)
                    conn.commit()
            print "+inserted %s visited urls to mysql" % (len(lst))
        except MySQLdb.Error, e:
            print "An error has been passed -> %s" %e
            sys.exit (1)
    if listtype=="backgrounds":
        try:
            cursor = hlsir.conn.cursor ()
            for item in lst:
                if item:
                    query = """ INSERT into visited_images (url) VALUES ('%s')""" % (item)
                    """print query"""
                    cursor.execute(query)
                    conn.commit()
            print "+inserted %s backgrounds to mysql" % (len(lst))
        except MySQLdb.Error, e:
            print "An error has been passed -> %s" %e
            sys.exit (1)
    if listtype=="noaccess":
        try:
            cursor = hlsir.conn.cursor ()
            for item in lst:
                if item:
                    query = """INSERT into visited_noaccess (url) VALUES ('%s') """ % (item)
                    """print query"""
                    cursor.execute(query)
                    conn.commit()
            print "+inserted %s noaccess to mysql" % (len(lst))
        except MySQLdb.Error, e:
            print "An error has been passed -> %s" %e
            sys.exit (1)
        
                
    
def writeMD5(fnMD5,lst,msg="",srt=1):
    "write MD5 list to hash (binary) file, print optional message, optionally sort before writing"
    try:
        cursor = hlsir.conn.cursor ()
        for item in lst:
            if item:
                query = """ INSERT into visited_hashes (hash) VALUES ('%s')""" % (item)
                """print query"""
                cursor.execute (query)
                conn.commit()
        print "+inserted %s hashes to mysql" % (len(lst))
    except MySQLdb.Error, e:
        print "An error has been passed -> %s" %e
        sys.exit (1)
    



def syncWithDB():
    global Q,tmp_md5,tmp_visited,tmp_backgrounds,tmp_noaccess
    writeMD5(fnMD5,tmp_md5s)
    writeList("visited",tmp_visited)
    writeList("backgrounds",tmp_backgrounds)
    writeList("noaccess",tmp_noaccess)
    writeQueue()
    readQueue()

def msearch(pat,str,fl=0):
    ret = []
    lastpos = 0;
    if type(pat) == types.StringType:          # if it's a string compile it
        r = re.compile(pat,fl)
    else:
        r = pat                                 # assume it's an re object
    while 1:
        m = r.search(str,lastpos)
        if not m: break
        ret.append(m.groups()[0])
        lastpos = m.start()+1
    return ret

def getHREFs(s, url):
    l = msearch(re_href,s,re.I)
    l = l + msearch(re_framesrc,s,re.I)
    l = l + msearch(re_metarefresh,s,re.I)
    if l:
        for x in range(len(l)):
            lx = urlparse.urljoin(url,l[x])
            if string.find(lx,'http://') >= 0:
                if not re_ads.search(lx):
                    #print "x",
                    if lx[-1]<>'/' and lx[-5]<>'.' and lx[-4]<>'.' and \
                            lx[-3]<>'.' and lx[-2]<>'.':
                        lx = lx + "/"
                    if lx not in visited:
                        if not re_badtypes.search(lx):
                            #print ",",
                            Q.put(lx)
                else:
                    pass
                    # print "! Bloody adverts."
    return len(l)


    
def getFileName(u,s):
    "return a new filename from URL to save graphic to"
    fn = ""
    num = 2
    i = string.rfind(u,'/')
    if i > -1:
        fn = savedir+u[i+1:]
        fp = os.path.splitext(fn)
        while os.path.exists(fn):
            fn = fp[0]+"_"+str(num)+fp[1]
            num = num + 1
        return fn
    return ""

def suckBG(u,url):
    "download the graphic, check for unique md5, save to unique filename"
    global bgBytes
    bget = None
    if u not in backgrounds and u not in tmp_backgrounds:
        try:
            bget = urllib.urlopen(u)
            if bget.info().getheader("Content-Type") and bget.info().getheader("Content-Type") != "image/jpeg" and bget.info().getheader("Content-length") < 15000 :
                "Let's be sure that we dont download image before knowing everything about it"
                print "+got image"
                bget.close()
                return
            else:
                btmp = bget.read()
                md = hashlib.md5(btmp).hexdigest()
        except Exception: 
            print "-couldn't download this picture"
            return
        if md not in md5s and md not in tmp_md5s :
                fn = getFileName(u,len(btmp))
                if fn: #if we have our image filename
                    fbg = open(fn,'wb') #open file for writing
                    fbg.write(btmp) # write it
                    fbg.close() #close it
                    bgBytes = bgBytes + len(btmp) #count size
                    fileHandler = Image.open(fn) #open file for analysis
                    fn_jpeg = fn
                    height = hlsir.reportShapeInfo(fn_jpeg)[1] 
                    width = hlsir.reportShapeInfo(fn_jpeg)[0]
                    if fileHandler.format == 'JPEG' and fileHandler.mode == 'RGB' and hlsir.reportShapeInfo(fn_jpeg)[0]>128 and hlsir.reportShapeInfo(fn_jpeg)[0]<1600 and hlsir.reportShapeInfo(fn_jpeg)[1]>128 and hlsir.reportShapeInfo(fn_jpeg)[1]<1600:
                        for x in range(0,sliceX):
                            for y in range(0,sliceY):
                                [h,l,s] = hlsir.convertJpgToHlsNumpy(fn_jpeg,x,y) # if hls is zero than image was too small
                                HLS_VECTOR[x,y] = [h,l,s]   
                        """print "This is HLS : %s " % (HLS_VECTOR)     """
                        print "\033[1m +vector commit! \033[0m"
                        hlsir.mysqlInsertImage(md,fn_jpeg,height,width,u,url,HLS_VECTOR)
                        hlsir.repetitiveness = 0
                        tmp_md5s.append(md)
        else:
            print "Inapropriate format of file"       
    else:
        print chrDupe+" MD5 fingerprint for '%s' exists." % u[string.rfind(u,'/')+1:]


# ===================================================================
# ===================================================================

# if an arg on command line then push it into the Queue so it's first
try:
    opts, args = getopt.getopt(sys.argv[1:], 'f:hr:s:')
except getopt.error, msg:
    print msg
    sys.exit(1)

for arg in args:
    Q.put(arg)

for opt,optarg in opts:
    if opt == '-h':
        print "Read the comments at the top of this script file for help."
        print "Reading the documentation may or may not be helpful, also."
        sys.exit()
    if opt == '-f':
        slist = string.split(optarg,";")
        print "Filtering Queue",slist
        readLists()
        for s in slist:
            filterQueue(s,chrMsg+" Filtered %s URLs with '%s'.")
        syncWithDB()
        sys.exit()
    if opt == '-r':
        print "Reducing Queue"
        readLists()
        reduceQueue(string.atoi(optarg),chrMsg+" Dropped %s Urls (approx %s%% of Queue).")
        syncWithDB()
        sys.exit()
    if opt == '-s':
        savedir = optarg


if not os.path.exists(savedir):
    print "The 'savedir' (%s) does not exist." % savedir
    print "Please edit 'savedir=\"%s\"' line near the top of the script." % savedir
    sys.exit()

savedir = savedir + os.sep


readLists()

for s in start:
    Q.put(s)

keepgoing = 1
visitcount = 0
kCrawled = 0
bgBytes = 0

try:
    os.remove(fnMsg)
except Exception:
    pass

try:
    while keepgoing and (not Q.empty()):
        hlsir.repetitiveness += 1
        cleanupQueue()
        if maxQueueSize and (Q.qsize() > maxQueueSize):
            reduceQueue(maxQueueSizeReduce,chrMsg+" Dropped %s Urls (approx %s%% of Queue).")
        if visitcount>maxVisitsBeforeSave:
            print "----DB sync----"
            visitcount=0
            syncWithDB()
            del tmp_md5s[:]
            del tmp_visited[:]
            del tmp_noaccess[:]
            del tmp_backgrounds[:]
            readLists()
        if not Q.empty():
            url = Q.get_nowait()
        if url and url in visited or url in tmp_visited:
            print "-visited"
            continue
        try:
            u = None
            """print "%s <- %s" % (url,maxVisitsBeforeSave-visitcount)"""
            try:
                u = urllib.urlopen(url)
            except:
                raise IOError, "couldn't open"
                tmp_noaccess.append(url) #we append the temporary list of visited urls to the global list
            if u==None:
                raise IOError, "couldn't retrieve"
                tmp_noaccess.append(url) #we append the temporary list of visited urls to the global list
            f = u.read()
            u.close()
            kCrawled = kCrawled + len(f)
            hrefs = getHREFs(f, url)
            print "+added %s items to queue." % (hrefs)
            back = hlsir.returnImagesList(url)
            if back:
                for picture in back:
                    if picture not in backgrounds and picture not in tmp_backgrounds:
                        """ print "%s" % picture  """
                        suckBG(picture,url) 
                        tmp_backgrounds.append(picture)
                        backgrounds.append(picture)
        except IOError,msg:
            print "-can't open %s (%s) - adding to noaccess" % (url,msg)
            tmp_noaccess.append(url)
        if os.path.exists(fnMsg):
            keepgoing = processMsg()
            os.remove(fnMsg)
        visitcount = visitcount + 1
        tmp_visited.append(url)
        print "*%s more attempts before queue reset" % (queue_cleanup_treshold - hlsir.repetitiveness)
        if hlsir.repetitiveness == queue_cleanup_treshold:
            hlsir.repetitiveness = 0
            print "*reseting queue (flushing)"
            cursor.execute ("delete from queue")
            while not Q.empty():
                tmp = Q.get_nowait()
            "*reseting queue (re-reading)"
            for url in start:
                try:    
                    query = "INSERT INTO queue (url) VALUES ('%s')" %(url)   
                    Q.put(url)   
                    cursor.execute (query) 
                    conn.commit()      
                except MySQLdb.Error, e:
                    print "An error has been passed -> %s" %e
                    sys.exit (1)
            


            
except KeyboardInterrupt:
    print " shutting down... %d urls in queue... " % Q.qsize()
    syncWithDB()
print "Crawled %d bytes of HTML, and %d bytes of backgrounds." % (kCrawled,bgBytes)

