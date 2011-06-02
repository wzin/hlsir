'''
Created on Jul 14, 2010

@author: wojciechziniewicz
TODO : hlsir.returnFLatHlsEquivalent() should accept "LIMIT sliceX*sliceY" format
'''

import Image,numpy,colorsys,os,MySQLdb,sys,urlparse
from BeautifulSoup import BeautifulSoup as bs
from urllib2 import urlopen
from HTMLParser import HTMLParseError


visited = []            # list of visited URLs
tmp_visited = []
noaccess = []           # list of urls which denied access or other error
tmp_noaccess = []
backgrounds = []        # list of background graphic urls
tmp_backgrounds = []
md5s = []               # list of MD5 fingerprints of all downloaded graphics
tmp_md5s = []
sliceX,sliceY = [5,5]
mysqlResultLimit = sliceX*sliceY
ALPHA         = 0.6
HLS_VECTOR    = numpy.zeros((sliceX,sliceY,3)) 
INPUT_VECTOR  = numpy.zeros((sliceX,sliceY,3))
IMPORTANCE_MATRIX = numpy.zeros((sliceX,sliceY))
frontend_upload_dir = "/home/wojtek/hlsir/frontend/upload"
crawler_img_library = "/home/wojtek/hlsir/img"
repetitiveness = 0

try:
    conn = MySQLdb.connect (host = "127.0.0.1", user = "crawleruser", passwd = "dup4", db = "crawler_live")
except MySQLdb.Error, e:
    print "Error %d: %s" % (e.args[0], e.args[1])
    sys.exit(1)

def normalizeRGBVector(color):
    return color[0]/255.0, color[1] / 255.0, color[2] / 255.0

def mysqlInsertImage(md5,os_path,height,width,URL,parent_url,HLS_VECTOR):
    try:
        cursor = conn.cursor ()
        query = " SELECT md5 from images where md5='%s' " % (md5)
        cursor.execute(query)
        md5_check = cursor.fetchone()
        if md5_check:
            print "-md already in db",
        else:
            query = """INSERT into images (md5,os_path,height,width,url,parent_url) VALUES ('%s','%s',%s,%s,'%s','%s')""" % (md5,os_path,height,width,URL,parent_url)
            """print query"""
            print query
            mysqlInsertVector(md5,HLS_VECTOR)
            cursor.execute (query)
            conn.commit()
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        sys.exit (1)


def mysqlInsertVector(md5,HLS_VECTOR):
    "inserts the given HLS vector into the database"
    cursor = conn.cursor ()
    try:
        query=" SELECT md5 from images where md5='%s' " % (md5)
        cursor.execute(query)
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        print "Didnt succeed inserting vector into DB"
    md5_check = cursor.fetchone()
    if 1==2 :
        print "Already in DB - skipping",
    else:
        try:
            arguments = "("
            values = "("
            n = 0
            cursor = conn.cursor ()
            #liczymy liste argumentow
            for n in range (0,sliceX*sliceY):
                h = "h%s" % n
                l = "l%s" % n
                s = "s%s" % n
                arguments = arguments + h +"," + l +"," + s +","
                if n == ((sliceX*sliceY)-1):
                    arguments += "image_md5)"
                    continue
            #liczymy liste wartosci
            n = 0
            for x in range (0,sliceX):
                for y in range (0,sliceY):
                    values = values + str(HLS_VECTOR[x,y,0])[0:10] + "," + str(HLS_VECTOR[x,y,1])[0:10] + "," + str(HLS_VECTOR[x,y,2])[0:10] + ","
                    if n == ((sliceX*sliceY)-1):
                        """add double quotation because of mysql syntax """
                        values += '"%s"'  % (md5)
                        values += ")"
                    n += 1
            query = ("""
            INSERT into vectors %s
            VALUES %s 
            """) % (arguments,values)
            print query
            cursor.execute (query)
            conn.commit()
        except MySQLdb.Error, e:
            print "Error %d: %s" % (e.args[0], e.args[1])
            print "Didnt succeed inserting vector into DB"

def reportShapeInfo(infile):
    global sliceX,sliceY
    fileHandler = Image.open(infile)
    imageArray = numpy.asarray(fileHandler)
    totalWidth = imageArray.shape[0]
    totalHeight = imageArray.shape[1]
    #If we have rest from image division
    if divmod(imageArray.shape[0] , sliceX)[1] != 0:
        widthUnit = divmod(imageArray.shape[0] , sliceX)[0]
    else:
        widthUnit = (divmod(imageArray.shape[0] , sliceX)[0])-1
    if divmod(imageArray.shape[1] , sliceY)[1] != 0:
        heightUnit = divmod(imageArray.shape[1] , sliceY)[0]
    else:
        heightUnit = (divmod(imageArray.shape[1] , sliceY)[0])-1
    return totalWidth,totalHeight,widthUnit,heightUnit #integers

    """Kazdy badany element, kazdego porownywanego wektora HLS moze miec 
    sztywno ustalona maksymalna roznice od korelowanego elementu wektora wejsciowego 
	-> result_image_url = set(hlsir.returnURLFromMD5(hlsir.constructHLSQuery(HLS_VECTOR,0.5,0.5,0.5,importance_matrix,0.2)))
	"""
	
def constructHLSQuery(hlsvector,h_weight,l_weight,s_weight,mask,modificator):
    try:
        arguments = ""
        n = 0
        cursor = conn.cursor ()
        for x in range (0,sliceX):
            for y in range (0,sliceY):
                if mask[x,y]==0:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "ABS(%s-%s)<%s AND ABS(%s-%s)<%s AND ABS(%s-%s)<%s" % (h,str(hlsvector[x,y,0])[0:6],h_weight,l,str(hlsvector[x,y,1])[0:6],l_weight,s,str(hlsvector[x,y,2])[0:6],s_weight)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + " AND "
                    else:
                        continue
                else:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "ABS(%s-%s)<(%s-%s) AND ABS(%s-%s)<(%s-%s) AND ABS(%s-%s)<(%s-%s)" % (h,str(hlsvector[x,y,0])[0:6],h_weight,modificator,l,str(hlsvector[x,y,1])[0:6],l_weight,modificator,s,str(hlsvector[x,y,2])[0:6],s_weight,modificator)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + " AND "
                    else:
                        continue     
        query = ("""
        SELECT image_md5 from vectors WHERE
        %s """) % (arguments) 
        """print query"""
        cursor.execute (query)
        md5 = cursor.fetchall()
        cursor.close ()

        return md5
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        print "Didnt succeed SELECTING vector FROM DB"

def HLSQueryCount(hlsvector,h_weight,l_weight,s_weight,mask,modificator):
    try:
        arguments = ""
        n = 0
        cursor = conn.cursor ()
        for x in range (0,sliceX):
            for y in range (0,sliceY):
                if mask[x,y]==0:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "ABS(%s-%s)<%s AND ABS(%s-%s)<%s AND ABS(%s-%s)<%s" % (h,str(hlsvector[x,y,0])[0:6],h_weight,l,str(hlsvector[x,
y,1])[0:6],l_weight,s,str(hlsvector[x,y,2])[0:6],s_weight)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + " AND "                    
		    else:
                        continue
                else:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "ABS(%s-%s)<(%s-%s) AND ABS(%s-%s)<(%s-%s) AND ABS(%s-%s)<(%s-%s)" % (h,str(hlsvector[x,y,0])[0:6],h_weight,modificator,l,str(hlsvector[x,y,1])[0:6],l_weight,modificator,s,str(hlsvector[x,y,2])[0:6],s_weight,modificator)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + " AND "
                    else:                        
			continue
        query = ("""
        SELECT count(image_md5) from vectors WHERE
        %s """) % (arguments)
        """print query"""
        cursor.execute (query)
        count = int(cursor.fetchone()[0])
        cursor.close ()
        return count
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        print "Didnt succeed SELECTING vector FROM DB"


def constructHLSQuery2(hlsvector,mask,modificator,global_deviation):
    """ Suma wszystkich wartosci bezwzglednych odstepstwa wszystkich elementow 
    kazdego wektora od kazdego elementu wektora wejsciowego
    mniejsza od np. 15  """
    try:
        arguments = "(SELECT(MIN("
        n = 0
        cursor = conn.cursor ()
        for x in range (0,sliceX):
            for y in range (0,sliceY):
                if mask[x,y]==1:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "ABS(%s-(%s+%s))+ABS(%s-(%s+%s))+ABS(%s-(%s+%s))" % (h,str(hlsvector[x,y,0])[0:6],modificator,l,str(hlsvector[x,y,1])[0:6],modificator,s,str(hlsvector[x,y,2])[0:6],modificator)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + "+"
                    else:
                        arguments = arguments+"))) < %s" % (global_deviation)
                        continue
                else:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "ABS(%s-%s)+ABS(%s-%s)+ABS(%s-%s)" % (h,str(hlsvector[x,y,0])[0:6],l,str(hlsvector[x,y,1])[0:6],s,str(hlsvector[x,y,2])[0:6])
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + "+"
                    else:
                        arguments = arguments+"))) < %s" % (global_deviation)
                        continue
        query = ("""
        SELECT image_md5 from vectors WHERE
        %s """) % (arguments) 
        """print query"""
        cursor.execute (query)
	md5 = cursor.fetchall()
        cursor.close ()
        return md5
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        print "Didnt succeed SELECTING vector FROM DB"

def HLSQuery2Count(hlsvector,mask,modificator,global_deviation):
    """ Suma wszystkich wartosci bezwzglednych odstepstwa wszystkich elementow 
    kazdego wektora od kazdego elementu wektora wejsciowego
    mniejsza od np. 15  """
    try:
        arguments = "(SELECT(MIN("
        n = 0
        cursor = conn.cursor ()
        for x in range (0,sliceX):
            for y in range (0,sliceY):
                if mask[x,y]==1:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "ABS(%s-(%s+%s))+ABS(%s-(%s+%s))+ABS(%s-(%s+%s))" % (h,str(hlsvector[x,y,0])[0:6],modificator,l,str(hlsvector[x,y,1])[0:6],modificator,s,str(hlsvector[x,y,2])[0:6],modificator)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + "+"
                    else:
                        arguments = arguments+"))) < %s" % (global_deviation)
                        continue
                else:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "ABS(%s-%s)+ABS(%s-%s)+ABS(%s-%s)" % (h,str(hlsvector[x,y,0])[0:6],l,str(hlsvector[x,y,1])[0:6],s,str(hlsvector[x,y,2])[0:6])
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + "+"
                    else:
                        arguments = arguments+"))) < %s" % (global_deviation)
                        continue
        query = ("""
        SELECT count(image_md5) from vectors WHERE
        %s """) % (arguments)
        """print query"""
        cursor.execute (query)
        count = int(cursor.fetchone()[0])
        cursor.close ()
        return count
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        print "Didnt succeed SELECTING vector FROM DB"


def constructHLSQuery3(hlsvector,parameter,mask,modificator):
    """Suma errorow na elementach kazdego wektora (slice'a) musi byc mniejsza
    od ustalonego parametru """
    try:
        arguments = "("
        n = 0
        cursor = conn.cursor ()
        for x in range (0,sliceX):
            for y in range (0,sliceY):
                if mask[x,y] == 1:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "(SELECT SUM(ABS(%s-%s)+ABS(%s-%s)+ABS(%s-%s)))<(%s-%s)" % (h,str(hlsvector[x,y,0])[0:6],l,str(hlsvector[x,y,1])[0:6],s,str(hlsvector[x,y,2])[0:6],parameter,modificator)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + " AND "
                    else:
                        arguments = arguments+" ) "
                        continue
                else:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "(SELECT SUM(ABS(%s-%s)+ABS(%s-%s)+ABS(%s-%s)))<%s" % (h,str(hlsvector[x,y,0])[0:6],l,str(hlsvector[x,y,1])[0:6],s,str(hlsvector[x,y,2])[0:6],parameter)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + " AND "
                    else:
                        arguments = arguments+" ) "
                        continue
        query = ("""
        SELECT image_md5 from vectors WHERE
        %s """) % (arguments) 
        """print query"""
        cursor.execute (query)
        md5 = cursor.fetchall()
        cursor.close ()
        return md5
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        print "Didnt succeed returning path from DB"

def HLSQuery3Count(hlsvector,parameter,mask,modificator):
    """Suma errorow na elementach kazdego wektora (slice'a) musi byc mniejsza
    od ustalonego parametru """
    try:
        arguments = "("
        n = 0
        cursor = conn.cursor ()
        for x in range (0,sliceX):
            for y in range (0,sliceY):
                if mask[x,y] == 1:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "(SELECT SUM(ABS(%s-%s)+ABS(%s-%s)+ABS(%s-%s)))<(%s-%s)" % (h,str(hlsvector[x,y,0])[0:6],l,str(hlsvector[x,y,1])[0:6],s,str(hlsvector[x,y,2])[0:6],parameter,modificator)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + " AND "
                    else:
                        arguments = arguments+" ) "
                        continue
                else:
                    h = "h%s" % n
                    l = "l%s" % n
                    s = "s%s" % n
                    n=n+1
                    arguments = arguments + "(SELECT SUM(ABS(%s-%s)+ABS(%s-%s)+ABS(%s-%s)))<%s" % (h,str(hlsvector[x,y,0])[0:6],l,str(hlsvector[x,y,1])[0:6],s,str(hlsvector[x,y,2])[0:6],parameter)
                    if n != ((sliceX*sliceY)):
                        arguments = arguments + " AND "
                    else:
                        arguments = arguments+" ) "
                        continue
        query = ("""
        SELECT count(image_md5) from vectors WHERE
        %s """) % (arguments)
        """print query"""
        cursor.execute (query)
        count = cursor.fetchone()
        cursor.close ()
        return int(count[0])
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        print "Didnt succeed returning path from DB"


def returnURLFromMD5(md5):
    try:
        urlret=[]
        cursor = conn.cursor()
        for item in md5:
            #print "Checking md5:%s" % (md5)
            query = "SELECT DISTINCT url from images where md5='%s'" % (item)
            cursor.execute (query)
            url = cursor.fetchone()
            urlret.append(url)
        return urlret
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        print "Didnt succeed returning path from DB"
        

def returnPathToFile(hlsquery):
    try:
        cursor = conn.cursor ()
        query = hlsquery
        cursor.execute(query)
        md5 = cursor.fetchone()
        cursor.execute("""SELECT DISTINCT os_path from images where md5=%s """,(md5))
        os_path = cursor.fetchone()
        return os_path
        cursor.close ()
    except MySQLdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        sys.exit (1)

        
def convertAnyFileToJPEG(infile):
    f, e = os.path.splitext(infile)
    outfile = f + ".jpg"
    if infile != outfile:
        try:
            file = Image.open(infile)
            file2 = file.convert("RGB")
            file2.save(outfile)
        except IOError:
            print "-cannot convert", infile
    return outfile #path

def returnImagesList(url):
    try:
        soup = bs(urlopen(url))
        urllist = []
        for image in soup.findAll("img"):
            if image['src'].lower().endswith("jpg") and (image['src'].lower().startswith("http://") or image['src'].lower().startswith("www")):
                urllist.append(image['src'])
            if image['src'].lower().endswith("jpg") and not image['src'].lower().startswith("http://"):
                hostname_uri = "http://" + urlparse.urlparse(url).hostname
                absolute_uri = hostname_uri + "/" + image['src']
                urllist.append(absolute_uri)
        return urllist
    except: HTMLParseError
    

def convertJpgToHlsNumpy(infile,X,Y):
    h,l,s = [0,0,0]
    newR,newG,newB = [0,0,0]
    fileHandler = Image.open(infile)
    widthUnit  = reportShapeInfo(infile)[2]
    heightUnit = reportShapeInfo(infile)[3]
    if reportShapeInfo(infile)[0]>64 and reportShapeInfo(infile)[0]<2048 and reportShapeInfo(infile)[1]>64 and reportShapeInfo(infile)[1]<2048: #protect us from processing too small objects
        for y in range(0+X*widthUnit,(X+1)*widthUnit):
            for x in range(0+Y*heightUnit,(Y+1)*heightUnit):
                R,G,B = fileHandler.getpixel((x,y))
                newR,newG,newB = [newR+R,newG+G,newB+B]        
        [avgR,avgG,avgB] = [ newR/(widthUnit*heightUnit), newG/(widthUnit*heightUnit) , newB/(widthUnit*heightUnit) ]
        [normalizedR,normalizedG,normalizedB] = normalizeRGBVector([avgR,avgG,avgB])
        h, l, s = colorsys.rgb_to_hls(normalizedR, normalizedG, normalizedB)
    else:
        print "-image not taken into account"
    return h,l,s # vector
