#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: University of Zurich
# Author: Rico Sennrich
# For licensing information, see LICENSE

# Evaluation functions for Bleualign


from __future__ import division
from operator import itemgetter


def evaluate(options, testalign, goldalign, log_function):
    goldalign = [(tuple(src),tuple(target)) for src,target in goldalign]
    
    results = {}
    paircounts = {}
    for pair in [(len(srclist),len(targetlist)) for srclist,targetlist in goldalign]:
        paircounts[pair] = paircounts.get(pair,0) + 1
        pairs_normalized = {}
        for pair in paircounts:
            pairs_normalized[pair] = (paircounts[pair],paircounts[pair] / float(len(goldalign)))
    
    log_function('\ngold alignment frequencies\n')
    for aligntype,(abscount,relcount) in sorted(list(pairs_normalized.items()),key=itemgetter(1),reverse=True):
        log_function(aligntype,end='')
        log_function(' - ',end='')
        log_function(abscount,end='')
        log_function(' ('+str(relcount)+')')
    
    log_function('\ntotal recall: ',end='')
    log_function(str(len(goldalign)) + ' pairs in gold')
    (tpstrict,fnstrict,tplax,fnlax) = recall((0,0),goldalign,[i[0] for i in testalign],log_function)
    results['recall'] = (tpstrict,fnstrict,tplax,fnlax)

    for aligntype in set([i[1] for i in testalign]):
        testalign_bytype = []
        for i in testalign:
            if i[1] == aligntype:
                testalign_bytype.append(i)
        log_function('precision for alignment type ' + str(aligntype) + ' ( ' + str(len(testalign_bytype)) + ' alignment pairs)')
        precision(goldalign,testalign_bytype,log_function)

    log_function('\ntotal precision:',end='')
    log_function(str(len(testalign)) + ' alignment pairs found')
    (tpstrict,fpstrict,tplax,fplax) = precision(goldalign,testalign,log_function)
    results['precision'] = (tpstrict,fpstrict,tplax,fplax)

    return results


def precision(goldalign, testalign, log_function):
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
                log_function('false positive: ',2)
                log_function((src,target),2)
    if tpstrict+fpstrict > 0:
        log_function('precision strict: ',end='')
        log_function((tpstrict/float(tpstrict+fpstrict)))
        log_function('precision lax: ',end='')
        log_function((tplax/float(tplax+fplax)))
        log_function('')
    else:
        log_function('nothing to find')

    return tpstrict,fpstrict,tplax,fplax


def recall(aligntype, goldalign, testalign, log_function):

    srclen,targetlen = aligntype

    if srclen == 0 and targetlen == 0:
        gapdists = [(0,0) for i in goldalign]
    elif srclen == 0 or targetlen == 0:
        log_function('nothing to find')
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
                    log_function('not found: ',2),
                    log_function(goldalign[i],2)

    if tpstrict+fnstrict>0:
        log_function('recall strict: '),
        log_function((tpstrict/float(tpstrict+fnstrict)))
        log_function('recall lax: '),
        log_function((tplax/float(tplax+fnlax)))
        log_function('')
    else:
        log_function('nothing to find')

    return tpstrict,fnstrict,tplax,fnlax


def finalevaluation(results, log_function):
    recall_value = [0,0,0,0]
    precision_value = [0,0,0,0]
    for i,k in list(results.items()):
        for m,j in enumerate(recall_value):
            recall_value[m] = j+ k['recall'][m]
        for m,j in enumerate(precision_value):
            precision_value[m] = j+ k['precision'][m]

    try:
        pstrict = (precision_value[0]/float(precision_value[0]+precision_value[1]))
    except ZeroDivisionError:
        pstrict = 0
    try:
        plax =(precision_value[2]/float(precision_value[2]+precision_value[3]))
    except ZeroDivisionError:
        plax = 0
    try:
        rstrict= (recall_value[0]/float(recall_value[0]+recall_value[1]))
    except ZeroDivisionError:
        rstrict = 0
    try:
        rlax=(recall_value[2]/float(recall_value[2]+recall_value[3]))
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

    log_function('\n=========================\n')
    log_function('total results:')
    log_function('recall strict: ',end='')
    log_function(rstrict)
    log_function('recall lax: ',end='')
    log_function(rlax)
    log_function('')

    log_function('precision strict: ',end='')
    log_function(pstrict)
    log_function('precision lax: '),
    log_function(plax)
    log_function('')
    
    log_function('f1 strict: ',end='')
    log_function(fstrict)
    log_function('f1 lax: ',end='')
    log_function(flax)
    log_function('')
