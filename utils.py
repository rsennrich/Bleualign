#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: University of Zurich
# Author: Rico Sennrich
# For licensing information, see LICENSE

# Evaluation functions for Bleualign

import sys
import os
from operator import itemgetter
sys.path.append(os.path.join(sys.path[0],'eval'))

loglevel = 1

def evaluate(article, options, testalign):
    global loglevel
    if 'loglevel' in options:
        loglevel = options['loglevel']
    
    gold1990map = {0:9,1:15,2:3,3:6,4:13,5:17,6:19}
    
    if options['eval'] == 1957:
        import golddev
        goldalign = golddev.goldalign
    elif options['eval'] == 1990:
        import goldeval
        goldalign = goldeval.gold[gold1990map[article]]
    
    goldalign = [(tuple(src),tuple(target)) for src,target in goldalign]
    
    results = {}
    paircounts = {}
    for pair in [(len(srclist),len(targetlist)) for srclist,targetlist in goldalign]:
        paircounts[pair] = paircounts.get(pair,0) + 1
        pairs_normalized = {}
        for pair in paircounts:
            pairs_normalized[pair] = (paircounts[pair],paircounts[pair] / float(len(goldalign)))
    
    print('\ngold alignment frequencies\n')
    for aligntype,(abscount,relcount) in sorted(pairs_normalized.items(),key=itemgetter(1),reverse=True):
        print(aligntype),
        print(' - '),
        print(abscount),
        print(' ('+str(relcount)+')')
    
    print('\ntotal recall: '),
    print(str(len(goldalign)) + ' pairs in gold')
    (tpstrict,fnstrict,tplax,fnlax) = recall((0,0),goldalign,[i[0] for i in testalign])
    results['recall'] = (tpstrict,fnstrict,tplax,fnlax)

    for aligntype in set([i[1] for i in testalign]):
        testalign_bytype = []
        for i in testalign:
            if i[1] == aligntype:
                testalign_bytype.append(i)
        print('precision for alignment type ' + str(aligntype) + ' ( ' + str(len(testalign_bytype)) + ' alignment pairs)')
        precision(goldalign,testalign_bytype)

    print('\ntotal precision:'),
    print(str(len(testalign)) + ' alignment pairs found')
    (tpstrict,fpstrict,tplax,fplax) = precision(goldalign,testalign)
    results['precision'] = (tpstrict,fpstrict,tplax,fplax)

    return results


def precision(goldalign,testalign):
    
    tpstrict=0
    tplax=0
    fpstrict=0
    fplax=0
    for (src,target) in [i[0] for i in testalign]:
        if (src,target) == ((),()):
            continue
        if (src,target) in goldalign:
            tpstrict +=1
            tplax += 1
        else:
            srcset, targetset = set(src), set(target)
            for srclist,targetlist in goldalign:
                #lax condition: hypothesis and gold alignment only need to overlap
                if srcset.intersection(set(srclist)) and targetset.intersection(set(targetlist)):
                    fpstrict +=1
                    tplax += 1
                    break
            else:
                fpstrict +=1
                fplax +=1
                log('false positive: ',2),
                log((src,target),2)
    if tpstrict+fpstrict > 0:
        print('precision strict: '),
        print((tpstrict/float(tpstrict+fpstrict)))
        print('precision lax: '),
        print((tplax/float(tplax+fplax)))
        print('')
    else:
        print('nothing to find')

    return tpstrict,fpstrict,tplax,fplax


def recall(aligntype,goldalign,testalign):

    srclen,targetlen = aligntype

    if srclen == 0 and targetlen == 0:
        gapdists = [(0,0) for i in goldalign]
    elif srclen == 0 or targetlen == 0:
        print('nothing to find')
        return
    else:
        gapdists = [(len(srclist),len(targetlist)) for srclist,targetlist in goldalign]

    tpstrict=0
    tplax=0
    fnstrict=0
    fnlax=0
    for i,pair in enumerate(gapdists):
        if aligntype == pair:
            (srclist,targetlist) = goldalign[i]
            if not srclist or not targetlist:
                continue
            elif (srclist,targetlist) in testalign:
                tpstrict +=1
                tplax +=1
            else:
                srcset, targetset = set(srclist), set(targetlist)
                for src,target in testalign:
                    #lax condition: hypothesis and gold alignment only need to overlap
                    if srcset.intersection(set(src)) and targetset.intersection(set(target)):
                        tplax +=1
                        fnstrict+=1
                        break
                else:
                    fnstrict+=1
                    fnlax+=1
                    log('not found: ',2),
                    log(goldalign[i],2)

    if tpstrict+fnstrict>0:
        print('recall strict: '),
        print((tpstrict/float(tpstrict+fnstrict)))
        print('recall lax: '),
        print((tplax/float(tplax+fnlax)))
        print('')
    else:
        print('nothing to find')

    return tpstrict,fnstrict,tplax,fnlax


def finalevaluation(results):
    recall = [0,0,0,0]
    precision = [0,0,0,0]
    for i,k in results.items():
        for m,j in enumerate(recall):
            recall[m] = j+ k['recall'][m]
        for m,j in enumerate(precision):
            precision[m] = j+ k['precision'][m]

    try:
        pstrict = (precision[0]/float(precision[0]+precision[1]))
    except ZeroDivisionError:
        pstrict = 0
    try:
        plax =(precision[2]/float(precision[2]+precision[3]))
    except ZeroDivisionError:
        plax = 0
    try:
        rstrict= (recall[0]/float(recall[0]+recall[1]))
    except ZeroDivisionError:
        rstrict = 0
    try:
        rlax=(recall[2]/float(recall[2]+recall[3]))
    except ZeroDivisionError:
        rlax = 0
    if (pstrict+rstrict) == 0:
        fstrict = 0
    else:
        fstrict=2*(pstrict*rstrict)/(pstrict+rstrict)
    if (plax+rlax) == 0:
        flax=0
    else:
        flax=2*(plax*rlax)/(plax+rlax)

    print('\n=========================\n')
    print('total results:')
    print('recall strict: '),
    print(rstrict)
    print('recall lax: '),
    print(rlax)
    print('')

    print('precision strict: '),
    print(pstrict)
    print('precision lax: '),
    print(plax)
    print('')
    
    print('f1 strict: '),
    print(fstrict)
    print('f1 lax: '),
    print(flax)
    print('')
    


def log(msg,level=1):
  if level <= loglevel:
    print(msg)