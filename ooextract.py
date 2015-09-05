#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import re
import xml.dom.minidom
import time
import zipfile

DEBUG=False
SourceSpectra=False
#SourceSpectra=True

def findNode(node,path):
    o=node
    last=path.pop()
    for tag in path:
        o=o.getElementsByTagName(tag)[0]
    return o.getElementsByTagName(last)
        

def getParents(node):
    source=None
    processed=None
    c1=node.firstChild
    for child in c1.childNodes:
        if child.nodeName=='sourceSpectra':
            source=child
        if child.nodeName=='certificates':
            processed=child
    return (source,processed)

def getText(node):
    element=node.firstChild
    if element and element.nodeType==xml.dom.Node.TEXT_NODE:
        return element.data.replace(',', ' ').encode('utf8')
    else:
        return None

def getWavelengths(node):
    values=findNode(node, ['channelWavelengths', 'double'])
    return [float(getText(v)) for v in values]

def getDarkSpectrum(node):
    values=findNode(node, ['darkSpectrum', 'pixelValues', 'double'])
    return [float(getText(v)) for v in values]

def getRefSpectrum(node):
    values=findNode(node, ['referenceSpectrum', 'pixelValues', 'double'])
    return [float(getText(v)) for v in values]

def getSourceSpectrum(node):
    values=findNode(node, ['pixelValues', 'double'])
    return [float(getText(v)) for v in values]

def getProcessedSpectrum(node):
    certs=node.getElementsByTagName('processedPixels')
    for o in certs:
        if len(o.childNodes)>10:
            break
    values=o.getElementsByTagName('double')
    return [float(getText(v)) for v in values]

def getTimestamp(node):
    ts=findNode(node, ['sourceSpectra', 'acquisitionTime', 'milliTime'])[0]
    return getText(ts)

def getMetadata(node):
    meta={}
    ss=node.getElementsByTagName('sourceSpectra')[0]
    meta['numberOfPixels']=int(getText(ss.getElementsByTagName('spectrometerNumberOfPixels')[0]))
    meta['maxIntensity']=float(getText(ss.getElementsByTagName('spectrometerMaximumIntensity')[0]))
    meta['Firmware']=getText(ss.getElementsByTagName('spectrometerFirmwareVersion')[0])
    meta['Serialnumber']=getText(ss.getElementsByTagName('spectrometerSerialNumber')[0])
    meta['nDarkPixels']=int(getText(ss.getElementsByTagName('spectrometerNumberOfDarkPixels')[0]))
    meta['user']=getText(ss.getElementsByTagName('userName')[0])
    meta['timestamp']=getTimestamp(node)
    meta['date']=time.ctime(float(meta['timestamp'])/1000.0)
    meta['integrationTime']=float(getText(ss.getElementsByTagName('integrationTime')[0]))
    meta['boxcarWidth']=int(getText(ss.getElementsByTagName('boxcarWidth')[0]))
    meta['saturated']=getText(ss.getElementsByTagName('saturated')[0])
    meta['scansToAverage']=int(getText(ss.getElementsByTagName('scansToAverage')[0]))
    return meta


def parseOOData(dom, source=False):
    metadata=getMetadata(dom)
    (source,processed)=getParents(dom)
    metadata['lam']=getWavelengths(source)
    if source:
        metadata['blackref']=()
        metadata['whiteref']=()
    else:
        metadata['blackref']=getDarkSpectrum(processed)
        metadata['whiteref']=getRefSpectrum(processed)
    metadata['Xsource']=getSourceSpectrum(source)
    metadata['Xprocessed']=getProcessedSpectrum(processed)
    return metadata

def writeSpectra(fid, X, descr):
    #fid=open(filename, 'w')
    fid.write('%s\t' %descr)
    for val in X:
        fid.write('%f\t' %val)
    #fid.close()
    fid.write('\n')

def writeDataVector(filename, v, title='lambda'):
    fid=open(filename, 'w')
    fid.write(title)
    fid.write('\n')
    for l in v:
        fid.write('%f\n' % l)
    fid.close()

def writeStrVector(filename, v, title='lambda'):
    with open(filename, 'w') as fid:
        fid.write(title)
        fid.write('\n')
        for l in v:
            fid.write('%s\n' % l)

def writeMeta(filename, meta):
    names=[
            'Firmware',
            'Serialnumber',
            'user',
            'timestamp',
            'date',
            'numberOfPixels',
            'maxIntensity',
            'integrationTime',
            'boxcarWidth',
            'scansToAverage',
            'saturated',
            ]
    with open(filename, 'w') as fid:
        for k in names:
            fid.write('%20s:   %s\n' % (k, meta[k]))



def parseFile(filename):
    illegal=[chr(x) for x in (0xa0, 0x89, 0x80, 0xe2, 0xb0, 0x88, 0x9e)]
    fid=zipfile.ZipFile(filename, 'r')
    names=fid.namelist()
    for name in names:
        if name.startswith('ps_'):
            break
    data=fid.read(name)
    fid.close()
    data=re.sub('['+''.join(illegal)+']', '', data.decode('latin1'))
    dom=xml.dom.minidom.parseString(data)
    return dom

def findLCB(args):
    """Finds the longest common beginning"""
    minlength=min([len(x) for x in args])
    
    for i in range(0,minlength):
        for s in args:
            if args[0][i]!=s[i]:
                return i
    return i

def sort(args):
    i=findLCB(args)
    s=[x[i:] for x in args]
    s.sort(key=lambda x,y: cmp(int(x), int(y)))
    return ['%s%s' % (args[0][0:i], x) for x in s]

def getSampleNums(args):
    i=findLCB(args)
    return [int(x[i:]) for x in args]

if __name__=='__main__':
    import sys

    args=sys.argv
    progname=args.pop(0)

    lam=[]
    data=[]
    meta={}
    times=[]

    if args[0]=='-f':
        opt=args.pop(0)
        outfilenamebase=args.pop(0)
    else:
        outfilenamebase='spectra'
    
    fid=open('%s.csv' % outfilenamebase, 'w')
    fids=open('%s-source.csv' % outfilenamebase, 'w')
    first=True

    N=len(args)
        
    basenames=[filename.split('.')[0].split('/').pop() for filename in args]
    print(basenames)
    samplenums=getSampleNums(basenames)
    records=[]
    for i in range(N):
        records.append((samplenums[i], basenames[i], args[i]))
    #records.sort(key=lambda x,y: cmp(int(x[0]), int(y[0])))
    
    for i in range(N):
        samplenum, basename, filename = records[i]
        dom=parseFile(filename)
        if DEBUG: 
            print("Parsing ", basename)
        info=parseOOData(dom, SourceSpectra)
        if first:
            writeSpectra(fid, info['lam'], 'Samplenum')
            writeSpectra(fids, info['lam'], 'Samplenum')
            first=False
        writeSpectra(fids, info['Xsource'], samplenum)
        writeSpectra(fid, info['Xprocessed'], samplenum)
        times.append('%s, %s' % (info['timestamp'], info['date']))
    fid.close()
    fids.close()

    writeMeta('%s-metadata.txt' % outfilenamebase, info)
    writeDataVector('%s-lambda.csv' % outfilenamebase, info['lam'], 'lambda')
    writeStrVector('%s-times.csv' % outfilenamebase, times, 'timestamp, time')



