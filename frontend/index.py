#!/usr/local/bin/python
            # directory for upload; will be created if doesn't exist
maxkb = 25000                    # maximum kilobytes to store before no more files accepted
link = "feedback.py"            # a page/url to link at the bottom of page after upload 
email = "wojciech.ziniewicz@gmail.com"     # where to email upload reports;
sendmail = "/usr/sbin/sendmail" # sendmail will email notification of uploads
#WTF
import cgitb
cgitb.enable()

import sys
sys.path.insert(0, '/Users/wojciechziniewicz/python/HLS/analysis/')
import os,cgi,glob,string,hlsir,Image,time

HLS_VECTOR = hlsir.HLS_VECTOR
dirUpload = hlsir.frontend_upload_dir

sys.stderr = sys.stdout
print "content-type: text/html\n"


def plural(s,num):
    "Make plural words nicely as possible."
    if num<>1:
        if s[-1] == "s" or s[-1] == "x":
            s = s + "e"
        s = s + "s"
    return s
    
def mailme(msg=""):
    "Quick and dirty, pipe a message to sendmail, appending various environmental variables to the message."
    if email:
        try:
            o = os.popen("%s -t" % sendmail,"w")
            o.write("To: %s\n" % email)
            o.write("From: %s\n" % email)
            o.write("Subject: %s\n" % "Upload Report")
            o.write("\n")
            o.write("%s\n" % msg)
            o.write("---------------------------------------\n")
            for x in [ 'REQUEST_URI','HTTP_USER_AGENT','REMOTE_ADDR','HTTP_FROM','REMOTE_HOST','REMOTE_PORT','SERVER_SOFTWARE','HTTP_REFERER','REMOTE_IDENT','REMOTE_USER','QUERY_STRING','DATE_LOCAL' ]:
                if os.environ.has_key(x):
                    o.write("%s: %s\n" % (x, os.environ[x]))
            o.write("---------------------------------------\n")
            o.close()                                        
        except IOError:
            pass                                        
            

########################################################################################
def form(posturl,button):
    "Print the main form."
    print """
    <html>
    <head>
    <meta http-equiv="content-type" content="text/html; charset=UTF-8">
    <title>HLS image search</title>
    <textarea id=csi style=display:none></textarea>
    <div id=mngb>
    <div id=gog>
    <div class=gbh style=left:0>
    </div>
    <div class=gbh style=right:0>
    </div>
    </div>
    </div>
    <center>
    <br clear=all id=lgpd>

<form action="%s" method="POST" enctype="multipart/form-data">

<input name="file.1" type="file" ">

<BR>
<P>
Slice priority :
<table>
<tr>
<td><input type=checkbox name=f0 value=1></td>
<td><input type=checkbox name=f1 value=1></td>
<td><input type=checkbox name=f2 value=1></td>
<td><input type=checkbox name=f3 value=1></td>
<td><input type=checkbox name=f4 value=1></td>
</tr>
<tr>
<td><input type=checkbox name=f5 value=1></td>
<td><input type=checkbox name=f6 value=1></td>
<td><input type=checkbox name=f7 value=1></td>
<td><input type=checkbox name=f8 value=1></td>
<td><input type=checkbox name=f9 value=1></td>
</tr>
<tr>
<td><input type=checkbox name=f10 value=1></td>
<td><input type=checkbox name=f11 value=1></td>
<td><input type=checkbox name=f12 value=1></td>
<td><input type=checkbox name=f13 value=1></td>
<td><input type=checkbox name=f14 value=1></td>
</tr>
<tr>
<td><input type=checkbox name=f15 value=1></td>
<td><input type=checkbox name=f16 value=1></td>
<td><input type=checkbox name=f17 value=1></td>
<td><input type=checkbox name=f18 value=1></td>
<td><input type=checkbox name=f19 value=1></td>
</tr>
<tr>
<td><input type=checkbox name=f20 value=1></td>
<td><input type=checkbox name=f21 value=1></td>
<td><input type=checkbox name=f22 value=1></td>
<td><input type=checkbox name=f23 value=1></td>
<td><input type=checkbox name=f24 value=1></td>
</tr>
</table>
<br>
<input name="submit" %s>
</form>

<div style="min-height:3.5em"><br>
</div>
<div id=res>
</div>
<span id=footer>
<center id=fctr>
<div style="font-size:10pt"><div id=fll style="margin:19px auto 19px auto;text-align:center">
<a href="about.html">About</a>
</div>
</div>
</center>
</span>
""" % (posturl,button)
########################################################################################

if os.environ.has_key("HTTP_USER_AGENT"):
    browser = os.environ["HTTP_USER_AGENT"]
else:
    browser = "No Known Browser"

if os.environ.has_key("SCRIPT_NAME"):
    posturl = os.environ["SCRIPT_NAME"]
else:
    posturl = ""

#posturl = "test.py"

kb = 0

fns = glob.glob(dirUpload+os.sep+"*")
for x in fns:
    kb = kb + os.stat(x)[6]

if kb/1024<maxkb:
    button = 'type="submit" value="Upload File"'
else:
    button = 'type="button" value="Upload Disabled (maximum KB reached)"'

data = cgi.FieldStorage()
keyList = data.keys()


if data.has_key("file.1"):  # we have uploads.

    if kb/1024>maxkb:
        print "<HTML><HEAD><TITLE>Upload Aborted</TITLE></HEAD><BODY>"
        msg = "There are already %.2f kb files in the upload area, which is more than the %s kb maximum. Therefore your files have not been accepted, sorry." % (kb / 1024.0, maxkb)
        print msg
        print "</BODY></HTML>"
        sys.exit()

    if not os.path.exists(dirUpload):
        os.mkdir(dirUpload,0777)

    fnList = []
    kbList = []
    kbCount = 0
    f = 1
    while f:
        key = "file.%s" % f
        if data.has_key(key):
            fn = data[key].filename
            if not fn:
                f = f + 1
                continue
            if string.rfind(data[key].filename,"\\") >= 0:
                fn = fn[string.rfind(data[key].filename,"\\"):]
            if string.rfind(data[key].filename,"/") >= 0:
                fn = fn[string.rfind(data[key].filename,"/"):]
            if string.rfind(data[key].filename,":") >= 0:
                fn = fn[string.rfind(data[key].filename,":"):]
            importance_matrix = hlsir.IMPORTANCE_MATRIX
            for item in keyList:
                idx = 0
                for x in range(0,hlsir.sliceX):
                    for y in range(0,hlsir.sliceY):
                        fname = "f%s" % (idx)
                        if item == fname:
                            importance_matrix[x,y]=1
                        idx+=1
            print "Importance matrix : %s" % (importance_matrix)
            
            o = open(dirUpload+os.sep+fn,"wb")
            o.write(data[key].value)
            o.close()

            fnList.append(fn)
            imagefile = dirUpload+os.sep+fn
            fileHandler = Image.open(imagefile)
            if fileHandler.format != "JPEG" or fileHandler.mode != "RGB":
                print "Invalid fileformat"
                sys.exit(0)
            else:
                file_jpeg = imagefile
                height = hlsir.reportShapeInfo(imagefile)[1] 
                width = hlsir.reportShapeInfo(imagefile)[0]
            
            for x in range(0,hlsir.sliceX):
                for y in range(0,hlsir.sliceY):
                    [H,L,S] = hlsir.convertJpgToHlsNumpy(file_jpeg,x,y)
                    HLS_VECTOR[x,y] = [H,L,S]
            
            print "<br>Source image:<br> <img src=upload/%s width=20%% height=20%%>" % (fn)
            """ method 1 """
            a = time.time()
            result_image_url = set(hlsir.returnURLFromMD5(hlsir.constructHLSQuery(HLS_VECTOR,0.5,0.5,0.5,importance_matrix,0.2)))
            sorted_image_url = set(result_image_url)
            print "<h1>Method1</h1>"
            print "<br>"
            print "Method 1 : We have 25 HLS input vectors. ",
            print "Each value of HLS vector is compared to each value of HLS input vector. ",
            print "Result of each subtraction should be lower than specified value."
            print "<br>"
            for i in sorted_image_url:
                print "<a href='%s'><img src=%s width=10%% height=10%%></a>" % (str(i)[2:-3],str(i)[2:-3])
            b = time.time()
            delta = b - a
            print "<br>It took %s seconds to perform query<br>" % (delta)
            
            """method 2"""
            a = time.time()
            for x in range(0,hlsir.sliceX):
                for y in range(0,hlsir.sliceY):
                    [H,L,S] = hlsir.convertJpgToHlsNumpy(file_jpeg,x,y)
                    HLS_VECTOR[x,y] = [H,L,S]
            """ Yepiee we have hls vector """
            result_image_url = set(hlsir.returnURLFromMD5(hlsir.constructHLSQuery2(HLS_VECTOR,importance_matrix,0.2,15)))
            sorted_image_url = set(result_image_url)
            print "<br><h1>Method2</h1><br>"
            print "<br>"
            print "Method 2 : We have 25 HLS input vectors. ",
            print "Each value of HLS vector is compared to each value of HLS input vector. ",
            print "For whole image, sum of absolute values of above 25x3 subtractions should be lower than specified value."
            print "<br>"
            for i in sorted_image_url:
                print "<a href='%s'><img src=%s width=10%% height=10%%></a>" % (str(i)[2:-3],str(i)[2:-3])
            b = time.time()
            delta = b - a
            print "<br>It took %s seconds to perform query<br>" % (delta)
             
            """method 3"""
            a = time.time()
            for x in range(0,hlsir.sliceX):
                for y in range(0,hlsir.sliceY):
                    [H,L,S] = hlsir.convertJpgToHlsNumpy(file_jpeg,x,y)
                    HLS_VECTOR[x,y] = [H,L,S]
            """ Yepiee we have hls vector """
            result_image_url = set(hlsir.returnURLFromMD5(hlsir.constructHLSQuery3(HLS_VECTOR,0.5,importance_matrix,0.2)))
            sorted_image_url = set(result_image_url)
            print "<br><h1>Method3</h1><br>"
            print "<br>"
            print "Method 3 : We have 25 HLS input vectors. ",
            print "Each value of HLS vector is compared to each value of HLS input vector. ",
            print "For each vector, sum of absolute values of 3 subtractions should be lower than specified value."
            print "<br>"
            for i in sorted_image_url:
                print "<a href='%s'><img src=%s width=10%% height=10%%></a>" % (str(i)[2:-3],str(i)[2:-3])
            b = time.time()
            delta = b - a
            print "<br>It took %s seconds to perform query<br>" % (delta) 
            
            a = time.time()
      
            
            kbList.append(len(data[key].value))
            kbCount = kbCount + len(data[key].value)
            f = f + 1
        else:
            f = 0


    print "<HTML><HEAD><TITLE>Upload Results</TITLE></HEAD><BODY>"
    if len(fnList):
        msg = "<H2>%s %s sum %.2f kb uploaded successfully:</H2>\n\n" % (len(fnList),plural("file",len(fnList)),kbCount / 1024.0)        
        print msg
        print "<HR><P><UL>"
        for x in range(0,len(fnList)):
            msg = msg + "  * %s (%.2f kb)\n" % (fnList[x],kbList[x] / 1024.0)
            print "<LI>%s (%.2f kb)" % (fnList[x],kbList[x] / 1024.0)
        print "</UL>"
        print "<P><HR>"
            
        print "Now a total of %.2f kb in %s %s in the upload area.<BR>" % ((kb + kbCount) / 1024.0,len(fnList)+len(fns),plural("file",len(fnList)+len(fns)))
        print 'Your browser I.D. is <B>%s</B>.' % browser
        
        print '<HR><CENTER><FONT SIZE="-1"><A HREF="%s">Thanks</A></FONT></CENTER>' % link
    else:
        print "No files were recieved."

    print "</BODY></HTML>"

else:
    form(posturl,button)

# the end

