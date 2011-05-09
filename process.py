#!/usr/bin/python
'''
Created on Jul 13, 2010

@author: wojciechziniewicz
'''
import sys,os
sys.path.append(os.getcwd())
import Image,getopt,hlsir

x = 0
y = 0
sliceX = hlsir.sliceX
sliceY = hlsir.sliceY
hlsVector = hlsir.HLS_VECTOR



try:
    opts, args = getopt.getopt(sys.argv[1:], 'f:x:y:h')
except getopt.error, msg:
    print msg
    sys.exit(1)

if not opts:
    print "You didnt give any arguments - exiting"
    
for opt,optarg in opts:
    if opt == '-h':
        print "The script takes one argument - filename of image."
        sys.exit()
    if opt == '-f':
        filename = optarg

if not os.path.exists(filename):
    print "The 'file' (%s) does not exist." % filename
    sys.exit()
if not filename:
    "Print - there's no filename."
    sys.exit()

fileHandler = Image.open(filename)
if fileHandler.format != "JPEG" or fileHandler.mode != "RGB":
    file_jpeg = hlsir.convertAnyFileToJPEG(filename)
else:
    file_jpeg = fileHandler
height = hlsir.reportShapeInfo(filename)[1] 
width = hlsir.reportShapeInfo(filename)[0]

for x in range(0,sliceX):
    for y in range(0,sliceY):
        [H,L,S] = hlsir.convertJpgToHlsNumpy(filename,x,y)
        hlsVector[x,y] = [H,L,S]


md5=hlsir.constructHLSQuery(hlsVector,0.8,0.8,0.8,1)
result=hlsir.returnImagePathFromMD5(md5)
print result
sys.exit(0);
#return result
