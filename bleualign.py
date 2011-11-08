#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2010 University of Zürich
# Author: Rico Sennrich <sennrich@cl.uzh.ch>
# For licensing information, see LICENSE

import sys
import os
import getopt
import time
import math
from xml.etree import cElementTree as ET
from operator import itemgetter, attrgetter
import gale_church
import score as bleu
sys.path.append(os.path.join(sys.path[0],'eval'))


try:
  import multiprocessing
  multiprocessing_enabled = 1
  number_of_threads = 4
except:
  multiprocessing_enabled = 0

#only consider target sentences for bleu-based alignment that are among top N alternatives for a given source sentence
maxalternatives = 3

#bleu scoring algorithm works with 4-grams by default. We got better results when using 2-grams (since there are less 0 scores then)
bleu_ngrams = 2

#consider N to 1 (and 1 to N) alignment in gapfilling (complexity is size_of_gap*value^2, so don't turn this unnecessarily high)
#also, there are potential precision issues.
#set to 1 to disable bleu-based 1 to N alignments and let gale & church fill the gaps
Nto1 = 2

#gapfillheuristics: what to do with sentences that aren't aligned one-to-one by the first BLEU pass, nor have a 1 to N alignment validated by BLEU?
#possible members are: bleu1to1, naive1to1, galechurch
#what they do is commented in the source code
gapfillheuristics = ["bleu1to1","galechurch"]

#defines amount of debugging output. can be overriden by --verbosity argument on command line
loglevel = 1

#defines string that identifies hard boundaries (articles, chapters etc.)
#string needs to be on a line of its own (see examples in eval directory)
#must be reliable (article i in the source text needs to correspond to article i in the target text)
end_of_article_marker = ".EOA"


def usage():
    bold = "\033[1m"
    reset = "\033[0;0m"
    italic = "\033[3m"

    print('\n\t All files need to be one sentence per line and have .EOA as a hard delimiter. --source, --target and --output are mandatory arguments, the others are optional.')
    print('\n\t' + bold +'--help' + reset + ', ' + bold +'-h' + reset)
    print('\t\tprint usage information\n')
    print('\t' + bold +'--source' + reset + ', ' + bold +'-s' + reset + ' file')
    print('\t\tSource language text.')
    print('\t' + bold +'--target' + reset + ', ' + bold +'-t' + reset + ' file')
    print('\t\tTarget language text.')
    print('\t' + bold +'--output' + reset + ', ' + bold +'-o' + reset + ' filename')
    print('\t\tOutput file: Will create ' + 'filename' + '-s and ' + 'filename' + '-t')
    print('\n\t' + bold +'--srctotarget' + reset + ' file')
    print('\t\tTranslation of source language text to target language. Needs to be sentence-aligned with source language text.')
    print('\t' + bold +'--targettosrc' + reset + ' file')
    print('\t\tTranslation of target language text to source language. Needs to be sentence-aligned with target language text.')
    print('\t' + bold +'--sourceids' + reset + ' file')
    print('\t\tOptional file that assigns a unique id to every source language sentence (needs to be int). Needs to be sentence-aligned with source language text. (Used for evaluation)')
    print('\t' + bold +'--targetids' + reset + ' file')
    print('\t\tOptional file that assigns a unique id to every target language sentence (needs to be int). Needs to be sentence-aligned with target language text. (Used for evaluation)')
    print('\n\t' + bold +'--factored' + reset)
    print('\t\tSource and target text can be factored (as defined by moses: | as separator of factors, space as word separator). Only first factor will be used for BLEU score.')
    print('\n\t' + bold +'--filter' + reset + ', ' + bold +'-f' + reset + ' option')
    print('\t\tFilters output. Possible options:')
    print('\t\t' + bold +'sentences' + reset + '\tevaluate each sentence and filter on a per-sentence basis')
    print('\t\t' + bold +'articles' + reset + '\tevaluate each article and filter on a per-article basis')
    print('\n\t' + bold +'--filterthreshold' + reset + ' int')
    print('\t\tFilters output to best XX percent. (Default: 90). Only works if --filter is set.')
    print('\n\t' + bold +'--filterlang' + reset)
    print('\t\tFilters out sentences/articles for which BLEU score between source and target is higher than that between translation and target (usually means source and target are in same language). Only works if --filter is set.')
    print('\t' + bold +'--galechurch' + reset)
    print('\t\tAlign the bitext using Gale and Church\'s algorithm (without BLEU comparison).')
    print('\t' + bold +'--printempty' + reset)
    print('\t\tAlso write unaligned sentences to file. By default, they are discarded.')
    print('\t' + bold +'--verbosity' + reset + ', ' + bold +'-v' + reset + ' int')
    print('\t\tVerbosity. Choose amount of debugging output. Default value 1; choose 0 for (mostly) quiet mode, 2 for verbose output')


def load_arguments():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "def:ho:s:t:v:", ["factored", "filter=", "filterthreshold=", "filterlang", "printempty", "deveval","eval", "help", "galechurch", "output=", "source=", "target=", "srctotarget=", "targettosrc=", "sourceids=", "targetids=","verbosity="])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err)) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    options = {}
    options['srcfile'] = None
    options['targetfile'] = None
    options['output'] = None
    options['sourceids'] = None
    options['targetids'] = None
    options['factored'] = False
    options['filter'] = None
    options['filterthreshold'] = 90
    options['filterlang'] = None
    options['srctotarget'] = []
    options['targettosrc'] = [] 
    options['eval'] = None
    options['galechurch'] = None
    options['verbosity'] = 1
    options['printempty'] = False

    bold = "\033[1m"
    reset = "\033[0;0m"

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-e", "--eval"):
            options['sourceids'] = os.path.join(sys.path[0],'eval','eval1989.id.de')
            options['targetids'] = os.path.join(sys.path[0],'eval','eval1989.id.fr')
            options['srcfile'] = os.path.join(sys.path[0],'eval','eval1989.de')
            options['targetfile'] = os.path.join(sys.path[0],'eval','eval1989.fr')
            options['eval'] = 1990
        elif o in ("-d", "--deveval"):
            options['sourceids'] = os.path.join(sys.path[0],'eval','eval1957.id.de')
            options['targetids'] = os.path.join(sys.path[0],'eval','eval1957.id.fr')
            options['srcfile'] = os.path.join(sys.path[0],'eval','eval1957.de')
            options['targetfile'] = os.path.join(sys.path[0],'eval','eval1957.fr')
            options['eval'] = 1957
        elif o in ("-o", "--output"):
            options['output'] = a
        elif o == "--factored":
            options['factored'] = True
        elif o in ("-f", "--filter"):
            if a in ['sentences','articles']:
              options['filter'] = a
            else:
              print('\nERROR: Valid values for option ' + bold + '--filter'+ reset +' are '+ bold +'sentences '+ reset +'and ' + bold +'articles'+ reset +'.')
              usage()
              sys.exit(2)
        elif o == "--filterthreshold":
            options['filterthreshold'] = float(a)
        elif o == "--filterlang":
            options['filterlang'] = True
        elif o == "--galechurch":
            options['galechurch'] = True
        elif o in ("-s", "--source"):
            options['srcfile'] = a
        elif o in ("-t", "--target"):
            options['targetfile'] = a
        elif o == "--srctotarget":
            options['srctotarget'].append(a)
        elif o == "--targettosrc":
            options['targettosrc'].append(a)
        elif o == "--sourceids":
            options['sourceids'] = a
        elif o == "--targetids":
            options['targetids'] = a
        elif o == "--printempty":
            options['printempty'] = True
        elif o in ("-v", "--verbosity"):
            global loglevel
            loglevel = int(a)
        else:
            assert False, "unhandled option"

    if not options['output']:
      log('WARNING: Output not specified. Just printing debugging output.',0)
    if not options['srcfile']:
      print('\nERROR: Source file not specified.')
      usage()
      sys.exit(2)
    if not options['targetfile']:
      print('\nERROR: Target file not specified.')
      usage()
      sys.exit(2)
    return options


def log(msg,level=1):
  global loglevel
  if level <= loglevel:
    print(msg)


def collect_article(src,srcids,srctotarget,target,targetids,targettosrc,options):
  EOF = 0
  
  while not EOF:
    SRC,TAR = 1,1
    counter = 0
    sourcelist,targetlist = [],[]
    translist1,translist2 = {},{}
  
    #read in source language article
    while SRC:
      trans = {}
      line = src.readline()
      if srcids:
        idline = srcids.readline()
      if srctotarget:
        for i,f in enumerate(srctotarget):
          trans[i] = f.readline()
        
      if line.rstrip() == end_of_article_marker:
        SRC = 0
        
      #EOF  
      if not line:
        EOF = 1
        SRC = 0
      
      if SRC and srcids:
        counter = int(idline[:-1])
      elif SRC:
        counter+=1
      if SRC and srctotarget:
        for i,f in enumerate(srctotarget):
          translist1[i] = translist1.get(i,[]) + [(counter,trans[i][:-1])]
      
      if SRC and options['factored']:
        rawline = ' '.join(word.split('|')[0] for word in line[:-1].split())
        sourcelist.append((counter,rawline,line[:-1]))
      elif SRC:
        sourcelist.append((counter,line[:-1]))

    counter = 0

    #read in target language article
    while TAR:
      trans = {}
      line = target.readline()
      if targetids:
        idline = targetids.readline()
      if targettosrc:
        for i,f in enumerate(targettosrc):
          trans[i] = f.readline()
        
      if line.rstrip() == end_of_article_marker:
        TAR = 0

      #EOF  
      if not line:
        EOF = 1
        TAR = 0

      if TAR and targetids:
        counter = int(idline[:-1])
      elif TAR:
        counter+=1
      if TAR and targettosrc:
        for i,f in enumerate(targettosrc):
          translist2[i] = translist2.get(i,[]) + [(counter,trans[i][:-1])]
          
      if TAR and options['factored']:
        rawline = ' '.join(word.split('|')[0] for word in line[:-1].split())
        targetlist.append((counter,rawline,line[:-1]))
      elif TAR:
        targetlist.append((counter,line[:-1]))
        
    yield sourcelist,targetlist,translist1,translist2


#takes a queue as argument and puts all articles to be aligned in it.
#best call this in a separate process because we limit the queue size for memory reasons
def tasks_producer(tasks,num_tasks,data):
    for i,task in enumerate(collect_article(*data)):
        num_tasks.value += 1
        tasks.put((i,task),True)
        
    #poison pills
    for i in range(number_of_threads):
        tasks.put((None,None))
    num_tasks.value -= 1 # only if this point is reached, process finishes when all tasks are done.

class Aligner:

    def __init__(self,options):
      self.src, self.target, self.srcidfile, self.targetidfile  = None,None,None,None
      self.out1, self.out2, self.out_bad1, self.out_bad2 = None,None,None,None
      self.srctargetswitch,self.finalbleu,self.before = 0,[],0
      self.srctotarget, self.targettosrc, self.sources_out,self.targets_out = [],[],[],[]
      self.options = options
      
      if options['srcfile']:
        self.src = open(options['srcfile'],'r')
      if options['targetfile']:
        self.target = open(options['targetfile'],'r')
        
      if options['output']:
        self.out1 = open(options['output'] + '-s','w')
        self.out2 = open(options['output'] + '-t','w')
      if options['output'] and options['filter']:
        self.out_bad1 = open(options['output'] + '-bad-s','w')
        self.out_bad2 = open(options['output'] + '-bad-t','w')

      #program will be run in 'wrong direction' if we only have targettosrc specified. make sure output is still written to the correct file
      if options['targettosrc'] and not options['srctotarget']:
        self.srctargetswitch = 1
        
      if options['sourceids']:
        self.srcidfile = open(options['sourceids'],'r')
      if options['targetids']:
        self.targetidfile = open(options['targetids'],'r')
        
      if options['srctotarget']:
        for f in options['srctotarget']:
          self.srctotarget.append(open(f,'r'))
      if options['targettosrc']:
        for f in options['targettosrc']:
          self.targettosrc.append(open(f,'r'))


    #takes care of multiprocessing; calls process() function for each article
    def mainloop(self):
      
      results = {}
      global number_of_threads
      global multiprocessing_enabled
      
      if multiprocessing_enabled:
        tasks = multiprocessing.Queue(number_of_threads+1)

        manager = multiprocessing.Manager()
        scores = manager.dict()
        num_tasks = manager.Value('i',1)
        scorers = [AlignMultiprocessed(tasks,self.options,scores)  for i in range(number_of_threads)]


        for p in scorers:
          p.start()

        #this function produces the alignment tasks for the consumers in scorers
        producer = multiprocessing.Process(target=tasks_producer,args=(tasks,num_tasks,(self.src,self.srcidfile,self.srctotarget,self.target,self.targetidfile,self.targettosrc,self.options)))
        producer.start()

        i = 0
        #get results from processed and call printout function
        while i < num_tasks.value:
            
            #wait till result #i is populated
            while True:
                try:
                    data,multialign,bleualign,scoredict = scores[i]
                    break
                except:
                    time.sleep(0.1)
                    continue

            (sourcelist,targetlist,translist1,translist2) = data
            self.scoredict = scoredict
            self.multialign = multialign
            self.bleualign = bleualign
            self.sourcelist = sourcelist
            self.targetlist = targetlist
            
            #normal case: translation from source to target exists
            if translist1:
                self.translist = translist1[0]
            
            #only translation from target to source provided. we swap them internally
            elif translist2:
                self.translist = translist2[0]
                self.sourcelist,self.targetlist = self.targetlist,self.sourcelist
                
            #no translation provided. we copy source sentences for further processing
            else:
                self.translist=self.sourcelist

            self.transids = [pair[0] for pair in self.translist]
            self.targetids = [pair[0] for pair in self.targetlist]
            self.sourceids = [pair[0] for pair in self.sourcelist]
            self.printout()

            if self.options['eval']:
                print('evaluation ' + str(i))
                results[i] = self.evaluate(i)
            
            del(scores[i])
            i += 1
            
      
      else:
        for i,(sourcelist,targetlist,translist1,translist2) in enumerate(collect_article(self.src,self.srcidfile,self.srctotarget,self.target,self.targetidfile,self.targettosrc,self.options)):
          log('reading in article ' + str(i) + ': ',1),
          self.multialign = self.process(sourcelist,targetlist,translist1,translist2)
          self.printout()
          if self.options['eval']:
            print('evaluation ' + str(i))
            results[i] = self.evaluate(i)
      
      if self.options['eval']:
        self.finalevaluation(results)
       
      if self.options['filter']:
        self.filtering()
          

    #Start different alignment runs depending on which and how many translations are sent to program; intersect results.
    def process(self,sourcelist,targetlist,translist1,translist2):
        
      multialign = []
        
      phase1 = []
      phase2 = []

      #do nothing if last line in file is .EOA or file is empty.
      if not targetlist or not sourcelist:
        log('WARNING: article is empty. Skipping.',0)
        return []

      log('processing',1)

      if translist2:
        phase2 = [0] * len(translist2)
        for j in translist2:
          log("computing alignment between targettosrc (file " + str(j) + ") and source text",1)
          self.sourcelist = targetlist
          self.targetlist = sourcelist
          self.translist = translist2[j]
          phase2[j] = self.align()        
      
      if translist1:
        phase1 = [0] * len(translist1)
        for j in translist1:
          log("computing alignment between srctotarget (file " + str(j) + ") and target text",1)
          self.sourcelist = sourcelist
          self.targetlist = targetlist
          self.translist = translist1[j]
          phase1[j] = self.align()
        
      if not (translist1 or translist2):
        log("no translation available: computing alignment between source and target text",1)
        self.sourcelist = sourcelist
        self.targetlist = targetlist
        self.translist = sourcelist
        phase1 = [self.align()]
        
      if len(phase1) > 1:
        log("intersecting all srctotarget alignments",1)
        phase1b = []
        for (pair,t) in phase1[0]:
          valid = 1
          for other in phase1[1:]:
            if pair in [pair2 for pair2,ty in other]:
              continue
            else:
              valid = 0
          if valid:
            phase1b.append((pair,t))
            
      elif phase1:
        phase1b = phase1[0]
      else: phase1b = []
            
      if len(phase2) > 1:
        log("intersecting all targettosrc alignments",1)
        phase2b = []
        for (pair,t) in phase2[0]:
          valid = 1
          for other in phase2[1:]:
            if pair in [pair2 for pair2,ty in other]:
              continue
            else:
              valid = 0
          if valid:
            phase2b.append((pair,t))
        
      elif phase2:
        phase2b = phase2[0]
      else: phase2b = []
        
      if phase1b and phase2b:
        log("intersecting both directions",1)
        phase3 = []
        phase2mirror = [(j,k) for ((k,j),t) in phase2b]
        for pair,t in phase1b:
          if pair in phase2mirror:
            phase3.append((pair,'INTERSECT: ' + t + ' - ' + phase2b[phase2mirror.index(pair)][1]))
        multialign = phase3
        
      elif phase1b:
        multialign = phase1b
        
      elif phase2b:
        multialign = [((j,k),t) for ((k,j),t) in phase2b]

      return multialign


    #Compute alignment for one article and one automatic translation.
    def align(self):
      
      if self.options["galechurch"]:
        self.transids = list(map(itemgetter(0),self.translist))
        self.targetids = list(map(itemgetter(0),self.targetlist))
        self.sourceids = list(map(itemgetter(0),self.sourcelist))
        self.multialign,self.bleualign,self.scoredict = [],[],{}
        churchaligns = self.gale_church(self.translist,self.targetlist)
        for src,target in churchaligns:
          self.addtoAlignments((src,target),'GALECHURCH')
        return self.multialign

      else:
        log('Evaluating sentences with bleu',1)
        self.scoredict = self.eval_sents(self.translist,self.targetlist)
        log('finished',1)
        log('searching for longest path of good alignments',1)
        self.pathfinder()
        log('finished',1)
        log(time.asctime(),2)
        log('filling gaps',1)
        self.gapfinder()
        log('finished',1)
        log(time.asctime(),2)
        return self.multialign


   #use this if you want to implement your own similarity score
    def eval_sents_dummy(self,translist,targetlist):
      global maxalternatives
      scoredict = {}
      
      for testID,testSent in translist:
        scores = []
        
        for refID,refSent in targetlist:
          score = 100-abs(len(testSent)-len(refSent)) #replace this with your own similarity score
          if score > 0:
            scores.append((score,refID,score))
        scoredict[testID] = sorted(scores,key=itemgetter(0),reverse=True)[:maxalternatives]
            
      return scoredict


    # given list of test sentences and list of reference sentences, calculate bleu scores
    #if you want to replace bleu with your own similarity measure, use eval_sents_dummy
    def eval_sents(self,translist,targetlist):
      
      global maxalternatives
      global bleu_ngrams
      
      scoredict = {}
      cooked_test = {}
      cooked_test2 = {}
      cooktarget =  [(items[0],bleu.cook_refs([items[1]],bleu_ngrams)) for items in targetlist]
      cooktarget = [(refID,(reflens, refmaxcounts, set(refmaxcounts))) for (refID,(reflens, refmaxcounts)) in cooktarget]


      for testID,testSent in translist:
        scorelist = []


        #copied over from bleu.py to minimize redundancy
        test_normalized = bleu.normalize(testSent)
        cooked_test["testlen"] = len(test_normalized)
        cooked_test["guess"] = [max(len(test_normalized)-k+1,0) for k in range(1,bleu_ngrams+1)]
        counts = bleu.count_ngrams(test_normalized, bleu_ngrams)
        
        #separate by n-gram length. if we have no matching bigrams, we don't have to compare unigrams
        ngrams_sorted = dict([(x,set()) for x in range(bleu_ngrams)])
        for ngram in counts:
            ngrams_sorted[len(ngram)-1].add(ngram)
            

        for (refID,(reflens, refmaxcounts, refset)) in cooktarget:
            
          ngrams_filtered = ngrams_sorted[bleu_ngrams-1].intersection(refset)
        
          if ngrams_filtered:
            cooked_test["reflen"] = reflens[0]
            cooked_test['correct'] = [0]*bleu_ngrams
            for ngram in ngrams_filtered:
              cooked_test["correct"][bleu_ngrams-1] += min(refmaxcounts[ngram], counts[ngram])
            
            for order in range(bleu_ngrams-1):
                for ngram in ngrams_sorted[order].intersection(refset):
                    cooked_test["correct"][order] += min(refmaxcounts[ngram], counts[ngram])

            #copied over from bleu.py to minimize redundancy
            logbleu = 0.0
            for k in range(bleu_ngrams):
                logbleu += math.log(cooked_test['correct'][k])-math.log(cooked_test['guess'][k])
            logbleu /= bleu_ngrams
            logbleu += min(0,1-float(cooked_test['reflen'])/cooked_test['testlen'])
            score = math.exp(logbleu)
            
            if score > 0:
                #calculate bleu score in reverse direction
                cooked_test2["guess"] = [max(cooked_test['reflen']-k+1,0) for k in range(1,bleu_ngrams+1)]
                logbleu = 0.0
                for k in range(bleu_ngrams):
                    logbleu += math.log(cooked_test['correct'][k])-math.log(cooked_test2['guess'][k])
                logbleu /= bleu_ngrams
                logbleu += min(0,1-float(cooked_test['testlen'])/cooked_test['reflen'])
                score2 = math.exp(logbleu)
                
                meanscore = (2*score*score2)/(score+score2)
                scorelist.append((meanscore,refID,cooked_test['correct']))
              
        scoredict[testID] = sorted(scorelist,key=itemgetter(0),reverse=True)[:maxalternatives]
        
      return scoredict


    #part of topological sorting algorithm
    def visit(self,src_n,target_n):
        if (src_n,target_n) in self.visited:
            return
        else:
            self.visited.add((src_n,target_n))
            self.remaining.remove((src_n,target_n))
            #instead of iterating through all edges, we compute them on the go
            for src_m,target_m in list(self.remaining):
                if src_m > src_n and target_m > target_n:
                  self.visit(src_m,target_m)
            self.ordered.append((src_n,target_n))


    #topological sorting algorithm
    #input self.alignList
    #output self.ordered
    def tsort(self):
        self.visited = set()
        self.ordered = []
        self.remaining = set(self.alignList)

        for src,target in self.alignList:
            self.visit(src,target)  

        del(self.visited)


    #find longest path of good BLEU alignments for which following conditions are true:
    #BLEU score is maximal, and path is monotonically ordered.
    def pathfinder(self):
        #populate list with all alignment candidates
        self.alignList = []
        scores = {}
        for itemTrans in [int(i[0]) for i in self.translist]:
            align = self.scoredict[itemTrans]
            if align:
                for alternative in align:
                  target = int(alternative[1])
                  score = alternative[0]
                  #score = 1 #for longest-path search
                  self.alignList.append((itemTrans,target))
                  scores[(itemTrans,target)] = score

        #topological sorting
        self.tsort()

        #longest-path search in acyclic directed graph through dynamic programming
        pred = len(self.ordered)*[(0,0)] # store predecessor for each node in longest path
        self.ordered.reverse()
        
        #initialize length of path to each node (from virtual start node)
        length_to = len(self.ordered)*[0]
        for i,(src,target) in enumerate(self.ordered):
            length_to[i] = scores[src,target]
        
        for i,(src_v,target_v) in enumerate(self.ordered):  
        
          #instead of iterating through list of edges, we calculate them on the go
          for j,(src_w,target_w) in enumerate(self.ordered):
              if target_w > target_v and src_w > src_v:
                  newscore = length_to[i] + scores[src_w,target_w]
                  if length_to[j] <= newscore:
                      length_to[j] = newscore
                      pred[j] = (src_v,target_v)


        #reconstruct longest path
        if self.ordered:
          next_translation, next_tar = self.ordered[length_to.index(max(length_to))]
        else:
          next_tar = 0

        self.bleualign = []
        while next_tar:
          self.bleualign.append((next_translation,next_tar))
          next_translation,next_tar=pred[self.ordered.index((next_translation,next_tar))]

      
    #find unaligned sentences and create work packets for gapfiller()
    #gapfiller() takes two sentence pairs and all unaligned sentences in between as arguments; gapfinder() extracts these.
    def gapfinder(self):
      
      self.multialign = []
      
      self.transids = list(map(itemgetter(0),self.translist))
      self.targetids = list(map(itemgetter(0),self.targetlist))
      self.sourceids = list(map(itemgetter(0),self.sourcelist))
      
      
      #find gaps: lastpair is considered pre-gap, pair is post-gap
      lastpair = ((),())
      src, target = None, None
      for src,target in reversed(self.bleualign):

        oldsrc,oldtarget = lastpair
        
        #identify gap sizes        
        if oldsrc:
          pregapsrc = self.transids.index(oldsrc[-1])
        else:
          pregapsrc = -1
        if oldtarget:
          pregaptarget = self.targetids.index(oldtarget[-1])
        else:
          pregaptarget = -1
        sourcegap = self.transids[pregapsrc+1:self.transids.index(src)]
        targetgap = self.targetids[pregaptarget+1:self.targetids.index(target)]
        
        if targetgap or sourcegap:
          lastpair = self.gapfiller(sourcegap,targetgap,lastpair,((src,),(target,)))
        else:
          self.addtoAlignments(lastpair)
          lastpair = ((src,),(target,))
        
      #search for gap after last alignment pair
      if src:
        pregapsrc = self.transids.index(src)
      else:
        pregapsrc = -1
      if target:
        pregaptarget = self.targetids.index(target)
      else:
        pregaptarget = -1
      sourcegap = self.transids[pregapsrc+1:]
      targetgap = self.targetids[pregaptarget+1:]
      if targetgap or sourcegap:
        lastpair = self.gapfiller(sourcegap,targetgap,lastpair,((),()))
      
      self.addtoAlignments(lastpair)


    #apply heuristics to align all sentences that remain unaligned after finding best path of 1-to-1 alignments
    #heuristics include bleu-based 1-to-n alignment and length-based alignment
    def gapfiller(self,sourcegap,targetgap,pregap,postgap):

      global gapfillheuristics
      global Nto1

      evalsrc = []
      evaltarget = []

      #compile list of sentences in gap that will be considered for BLEU comparison
      if Nto1 > 1 or "bleu1to1" in gapfillheuristics:

        #concatenate all sentences in pregap alignment pair
        tmpstr =  ''.join([self.translist[self.transids.index(i)][1] for i in pregap[0]])
        evalsrc.append((pregap[0],tmpstr))

        #concatenate all sentences in pregap alignment pair
        tmpstr =  ''.join([self.targetlist[self.targetids.index(i)][1] for i in pregap[1]])
        evaltarget.append((pregap[1],tmpstr))
        
        #search will be pruned to this window
        if "bleu1to1" in gapfillheuristics:
          window = 10 + Nto1
        else:
          window = Nto1
        
        for src in [j for i,j in enumerate(sourcegap) if (i < window or len(sourcegap)-i <= window)]:
          ID,Sent = self.translist[self.transids.index(src)]
          evalsrc.append(((ID,),Sent))
        
        for target in [j for i,j in enumerate(targetgap) if (i < window or len(targetgap)-i <= window)]:
          ID,Sent = self.targetlist[self.targetids.index(target)][:2]
          evaltarget.append(((ID,),Sent))
        
        #concatenate all sentences in pregap alignment pair
        tmpstr =  ''.join([self.translist[self.transids.index(i)][1] for i in postgap[0]])
        evalsrc.append((postgap[0],tmpstr))
        
        #concatenate all sentences in postgap alignment pair
        tmpstr =  ''.join([self.targetlist[self.targetids.index(i)][1] for i in postgap[1]])
        evaltarget.append((postgap[1],tmpstr))

        nSrc = {}
        for n in range(2,Nto1+1):
          nSrc[n] = self.createNSents(evalsrc,n)
        for n in range(2,Nto1+1):
          evalsrc += nSrc[n]

        nTar = {}
        for n in range(2,Nto1+1):
          nTar[n] = self.createNSents(evaltarget,n)
        for n in range(2,Nto1+1):
          evaltarget += nTar[n]
        
        scoredict = self.eval_sents(evalsrc,evaltarget)

      
      while sourcegap or targetgap:
        pregapsrc,pregaptarget = pregap
        postgapsrc,postgaptarget = postgap
          
        if sourcegap and Nto1 > 1:
          
          #try if concatenating source sentences together improves bleu score (beginning of gap)
          try:
            oldscore,oldtarget,oldcorrect = scoredict[pregapsrc][0]
          except (ValueError,IndexError,KeyError):
            oldscore,oldtarget,oldcorrect = 0, 0, 0
          combinedID = tuple(list(pregapsrc)+[sourcegap[0]])
          try:
            newscore,newtarget,newcorrect = scoredict[combinedID][0]
          except (ValueError,IndexError,KeyError):
            newscore,newtarget, newcorrect = 0, 0,0
          if newscore > oldscore and newcorrect > oldcorrect and newtarget == pregaptarget:
              #print('\nsource side: ' + str(combinedID) + ' better than ' + str(pregapsrc))
              pregap = (combinedID,pregaptarget)
              del(sourcegap[0])
              continue
            
          #try if concatenating source sentences together improves bleu score (end of gap)
          try:
            oldscore,oldtarget,oldcorrect = scoredict[postgapsrc][0]
          except (ValueError,IndexError,KeyError):
            oldscore,oldtarget,oldcorrect = 0, 0,0
          combinedID = tuple([sourcegap[-1]] + list(postgapsrc))
          try:
            newscore,newtarget, newcorrect = scoredict[combinedID][0]
          except (ValueError,IndexError,KeyError):
            newscore,newtarget, newcorrect = 0, 0, 0
          if newscore > oldscore  and newcorrect > oldcorrect and newtarget == postgaptarget:
              #print('\nsource side: ' + str(combinedID) + ' better than ' + str(postgapsrc))
              postgap = (combinedID,postgaptarget)
              sourcegap.pop()
              continue

        if targetgap  and Nto1 > 1:
          
          #try if concatenating target sentences together improves bleu score (beginning of gap)
          try:
            newscore,newtarget,newcorrect = scoredict[pregapsrc][0]
            if newtarget != pregaptarget:
              valid = 1
              for i in newtarget:
                if not (i in targetgap or i in pregaptarget):
                  valid = 0
              if valid:
                #print('\ntarget side: ' + str(newtarget) + ' better than ' + str(pregaptarget))
                pregap = (pregapsrc,newtarget)
                for i in newtarget:
                  if i in targetgap:
                    del(targetgap[targetgap.index(i)])
                continue
          except (ValueError,IndexError,KeyError):
            pass

          #try if concatenating target sentences together improves bleu score (end of gap)
          try:
            newscore,newtarget,newcorrect = scoredict[postgapsrc][0]
            if newtarget != postgaptarget:
              valid = 1
              for i in newtarget:
                if not (i in targetgap or i in postgaptarget):
                  valid = 0
              if valid:
                #print('\ntarget side: ' + str(newtarget) + ' better than ' + str(postgaptarget))
                postgap = (postgapsrc,newtarget)
                for i in newtarget:
                  if i in targetgap:
                    del(targetgap[targetgap.index(i)])
                continue
          except (ValueError,IndexError,KeyError):
            pass
        
        #concatenation didn't help, and we still have possible one-to-one alignments
        if sourcegap and targetgap:

          #align first two sentences if BLEU validates this
          if "bleu1to1" in gapfillheuristics:
            try:
              besttarget = scoredict[(sourcegap[0],)][0][1]
            except:
              besttarget = 0
            if besttarget == (targetgap[0],):
              self.addtoAlignments(pregap)
              #print('\none-to-one: ' + str((sourcegap[0],)) + ' to' + str((targetgap[0],)))
              pregap = ((sourcegap[0],),besttarget)
              del(sourcegap[0])
              del(targetgap[0])
              continue

          #naive approach: take first two sentences and align them
          if "naive1to1" in gapfillheuristics:
            self.addtoAlignments(pregap)
            #print('\none-to-one: ' + str((sourcegap[0],)) + ' to' + str((targetgap[0],)))
            pregap = ((sourcegap[0],),(targetgap[0],))
            del(sourcegap[0])
            del(targetgap[0])
            continue
          
          #Alternative approach: use Gale & Church.
          if "galechurch" in gapfillheuristics and (max(len(targetgap),len(sourcegap))<4 or max(len(targetgap),len(sourcegap))/min(len(targetgap),len(sourcegap)) < 2):
            tempsrcgap = []
            for src in sourcegap:
              tempsrcgap.append(self.translist[self.transids.index(src)])
              #tempsrcgap.append(((ID,),Sent))
            
            temptargetgap = []
            for target in targetgap:
              temptargetgap.append(self.targetlist[self.targetids.index(target)])
              #temptargetgap.append(((ID,),Sent))
              
            churchaligns = self.gale_church(tempsrcgap,temptargetgap)

            for src,target in churchaligns:
              self.addtoAlignments((src,target),'GALECHURCH')
            break
         
          #no valid gapfiller left. break loop and ignore remaining gap
          break
      
        break
        
      if not pregap in [i[0] for i in self.multialign]:
        self.addtoAlignments(pregap)
      return postgap


  #Take list of (ID,Sentence) tuples for two language pairs and calculate Church & Gale alignment
  #Then transform it into this program's alignment format
    def gale_church(self,tempsrcgap,temptargetgap):

      #get sentence lengths in characters
      srclengths = [[len(i[1].strip()) for i in tempsrcgap]]
      targetlengths = [[len(i[1].strip()) for i in temptargetgap]]
      
      #call gale & church algorithm
      pairs = sorted(list((gale_church.align_texts(srclengths, targetlengths)[0])), key=itemgetter(0))

      idict = {}
      jdict = {}
      newpairs = []

      #store 1-to-n alignments in single pairs of tuples (instead of using multiple pairs of ints)
      for i,j in pairs:
        if i in idict and j in jdict:
            done = 0
            for iold1, jold1 in newpairs:
              if done:
                break
              if i in iold1:
                for iold2, jold2 in newpairs:
                  if done:
                    break
                  if j in jold2:
                    if not (iold1,jold1) == (iold2,jold2):
                      del(newpairs[newpairs.index((iold1,jold1))])
                      del(newpairs[newpairs.index((iold2,jold2))])
                      inew = tuple(sorted(list(iold1)+list(iold2)))
                      jnew = tuple(sorted(list(jold1)+list(jold2)))
                      newpairs.append((inew,jnew))
                    done = 1
                    break

        elif i in idict:
          for iold, jold in newpairs:
            if i in iold:
              jnew = tuple(sorted(list(jold)+[j]))
              newpairs[newpairs.index((iold,jold))] = (iold,jnew)
              jdict[j] = 0
              break

        elif j in jdict:
          for iold, jold in newpairs:
            if j in jold:
              inew = tuple(sorted(list(iold)+[i]))
              newpairs[newpairs.index((iold,jold))] = (inew,jold)
              idict[i] = 0
              break

        else:
          idict[i] = 0
          jdict[j] = 0
          newpairs.append(((i,),(j,)))

      #Go from Church & Gale's numbering to our IDs
      outpairs = []
      for i,j in newpairs:
        srcID = []
        targetID = []
        for src in i:
          srcID.append(tempsrcgap[src][0])
        for target in j:
          targetID.append(temptargetgap[target][0])
        #print('\nChurch & Gale: ' + str(tuple(srcID)) + ' to ' + str(tuple(targetID)))
        outpairs.append((tuple(srcID),tuple(targetID)))
        
      return outpairs


    #get a list of (ID,Sentence) tuples and generate bi- or tri-sentence tuples
    def createNSents(self,l,n=2):
      
      out = []
      
      for i in range(len(l)-n+1):
        IDs = tuple([k for sublist in l[i:i+n] for k in sublist[0]])
        Sents = " ".join([k[1] for k in l[i:i+n]])
        out.append((IDs,Sents))
      
      return out
          

    def addtoAlignments(self,pair,aligntype=None):
      if not (pair[0] and pair[1]):
        return
      if aligntype:
        self.multialign.append((pair,aligntype))
      else:
        src,target = pair
        if len(src) == 1 and len(target) == 1 and (src[0],target[0]) in self.bleualign:
          self.multialign.append((pair,"BLEU"))
        else:
          self.multialign.append((pair,"GAPFILLER"))

          
    #print out some debugging info, and print output to file
    def printout(self):

      multialignsrccount = sum([len(i[0][0]) for i in self.multialign])
      multialigntargetcount = sum([len(i[0][1]) for i in self.multialign])

      global loglevel

      log("Results of BLEU 1-to-1 alignment",2)
      if loglevel >= 2:
        bleualignsrc = list(map(itemgetter(0),self.bleualign))
        for sourceid in [i[0] for i in self.translist]:
          if sourceid in bleualignsrc:
            print('\033[92m' + str(sourceid) + ": "),
            print(str(self.bleualign[bleualignsrc.index(sourceid)][1]) + '\033[1;m')
          else:
            print('\033[1;31m'+str(sourceid) + ": unaligned. best cand "),
            bestcand = self.scoredict.get(sourceid,[])
            if bestcand:
              bestcand = bestcand[0][1]
            print(str(bestcand)+'\033[1;m')
            
        if self.translist and self.targetlist:
          log("\n" + str(len(self.bleualign)) + ' out of ' + str(len(self.translist)) + ' source sentences aligned by BLEU ' + str(100*len(self.bleualign)/float(len(self.translist))) + '%',2)
        
          log("after gap filling, " + str(multialignsrccount) + ' out of '+ str(len(self.translist)) + ' source sentences aligned ' + str(100*multialignsrccount/float(len(self.translist))) + '%')
          log("after gap filling, " + str(multialigntargetcount) + ' out of '+ str(len(self.targetlist)) + ' target sentences aligned ' + str(100*multialigntargetcount/float(len(self.targetlist))) + '%',2)

      sources = []
      translations = []
      targets = []
      sources_factored = []
      targets_factored = []
      self.multialign = sorted(self.multialign,key=itemgetter(0))
      sentscores = {}
      lastsrc,lasttarget = 0,0
      for j,(src,target) in enumerate([i[0] for i in self.multialign]):
        if self.srctargetswitch:
          src,target = target,src
        
        if self.options['printempty']:
            if src[0] != lastsrc + 1:
                sources.extend([self.sourcelist[self.sourceids.index(ID)][1] for ID in range(lastsrc+1,src[0])])
                targets.extend(['' for ID in range(lastsrc+1,src[0])])
                translations.extend(['' for ID in range(lastsrc+1,src[0])])
                
            if target[0] != lasttarget + 1:
                sources.extend(['' for ID in range(lasttarget+1,target[0])])
                targets.extend([self.targetlist[self.targetids.index(ID)][1] for ID in range(lasttarget+1,target[0])])
                translations.extend(['' for ID in range(lasttarget+1,target[0])])
        
        sources.append(' '.join([self.sourcelist[self.sourceids.index(ID)][1] for ID in src]))
        targets.append(' '.join([self.targetlist[self.targetids.index(ID)][1] for ID in target]))
        translations.append(' '.join([self.translist[self.transids.index(ID)][1] for ID in src]))
        
        lastsrc = src[-1]
        lasttarget = target[-1]

        if self.options['factored']:
          sources_factored.append(' '.join([self.sourcelist[self.sourceids.index(ID)][2] for ID in src]))
          targets_factored.append(' '.join([self.targetlist[self.targetids.index(ID)][2] for ID in target]))

        if self.options['filter'] == 'sentences':
          sentscore = self.score_article([translations[-1]],[targets[-1]])
          sentscore2 = self.score_article([sources[-1]],[targets[-1]])
          if sentscore2 > sentscore and options['filterlang']:
            if self.options['factored']:
              self.out_bad1.write(sources_factored[-1] + '\n')
              self.out_bad2.write(targets_factored[-1] + '\n')
            else:
              self.out_bad1.write(sources[-1] + '\n')
              self.out_bad2.write(targets[-1] + '\n')
          else:
            if sentscore > 0:
              sentscorex = self.score_article([targets[-1]],[translations[-1]])
              newsentscore = (2*sentscore*sentscorex)/(sentscore+sentscorex)
            else:
              newsentscore = 0
            sentscores[j]=newsentscore
  
      #confidence measure
      if self.options['filter'] == 'sentences':
        for j,(src,target) in enumerate([i[0] for i in self.multialign]):
          if j in sentscores: # false if sentence pair has been filtered out by language filter
            confidence = sentscores[j]
            self.finalbleu.append((confidence,sentscores.get(j),self.before,self.before+1))
            self.before = self.before + 1
            self.sources_out.append(sources[j])
            self.targets_out.append(targets[j])
          
      if self.options['filter'] == 'articles':
        articlescore = self.score_article(translations,targets)
        articlescore2 = self.score_article(sources,targets)
          
        log('\nBLEU score for article: ' + str(articlescore) + ' / ' + str(articlescore2),1)

        if articlescore2 > articlescore and options['filterlang']:
          if self.options['factored']:
            sources,targets = sources_factored,targets_factored
          if self.srctargetswitch:
            sources,targets = targets,sources
          for i,line in enumerate(sources):
            self.out_bad1.write(line + '\n')
            self.out_bad2.write(targets[i] + '\n')
        else:
          articlescorex = self.score_article(targets,translations)
          if articlescore > 0:
            articlescore = (articlescore*articlescorex*2)/(articlescore+articlescorex)
          before = self.before
          after = self.before + len(self.multialign)
          self.before = after
          self.finalbleu.append((articlescore,articlescore2,before,after))
         
          if self.options['factored']:
            sources,targets = sources_factored,targets_factored
            
          self.sources_out += sources
          self.targets_out += targets


      log("\nfinished with article",1)
      log("\n====================\n",1)

      if self.out1 and self.out2 and not options['filter']:
        if self.options['factored']:
          sources,targets = sources_factored,targets_factored
        if self.srctargetswitch:
          sources,targets = targets,sources
        for line in sources:
          self.out1.write(line + '\n')
        for line in targets:
          self.out2.write(line + '\n')
       
       
    #get BLEU score for article pair
    def score_article(self,test,ref):
      global bleu_ngrams
      refs = [bleu.cook_refs([refSent],bleu_ngrams) for refSent in ref]
      testcook = []

      for i,line in enumerate(test):
        testcook.append(bleu.cook_test(line,refs[i],bleu_ngrams))
        
      score = bleu.score_cooked(testcook,bleu_ngrams)
      return score


    #filter bad sentence pairs / article pairs
    def filtering(self):
      
      self.finalbleu = sorted(self.finalbleu,key=itemgetter(0),reverse=True)
      log(self.finalbleu,2)
      
      totallength=0
      totalscore=0
      
      for (articlescore,articlescore2,before,after) in self.finalbleu:
        length = after-before
        totallength += length
        totalscore += articlescore*length
        
      averagescore = totalscore/totallength
      log("The average BLEU score is: " + str(averagescore),1)
      
      goodlength = totallength*options['filterthreshold']/float(100)
      totallength = 0
      
      bad_percentiles = []
      for i,(articlescore,articlescore2,before,after) in enumerate(self.finalbleu):
        length = after-before
        totallength += length
        if totallength > goodlength:
          bad_percentiles = self.finalbleu[i+1:]
          log("\nHow about throwing away the following " + self.options['filter'] + "?\n",2)
          log(bad_percentiles,2)
          if loglevel >= 3:
            for score,score2,start,end in bad_percentiles:
              for i in range(start,end):
                log(score,3)
                log(self.sources_out[i],3)
                log(self.targets_out[i],3)
                log('-----------------',3)
          break

      stopwrite = dict([(i[2],1) for i in bad_percentiles])
      resumewrite = dict([(i[3],1) for i in bad_percentiles])
      stopped = 0

      if self.out1 and self.out2 and self.out_bad1 and self.out_bad2:
        if self.srctargetswitch:
          self.sources_out,self.targets_out = self.targets_out,self.sources_out
        for i,line in enumerate(self.sources_out):
          if i in resumewrite:
            stopped = 0
          if i in stopwrite:
            stopped = 1
          if stopped:
            self.out_bad1.write(line + '\n')
            self.out_bad2.write(self.targets_out[i] + '\n')
          else:
            self.out1.write(line + '\n')
            self.out2.write(self.targets_out[i] + '\n')


    def evaluate(self,i):
      
      gold1990map = {0:9,1:15,2:3,3:6,4:13,5:17,6:19}
      
      if self.options['eval'] == 1957:
        import golddev
        goldalign = golddev.goldalign
      elif self.options['eval'] == 1990:
        import goldeval
        goldalign = goldeval.gold[gold1990map[i]]
      
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
        #self.recall(aligntype,goldalign,[i[0] for i in self.multialign])
      
      print('\ntotal recall: '),
      print(str(len(goldalign)) + ' pairs in gold')
      (tpstrict,fnstrict,tplax,fnlax) = self.recall((0,0),goldalign,[i[0] for i in self.multialign])
      results['recall'] = (tpstrict,fnstrict,tplax,fnlax)

      #for gapdist in set([(len(i[0]),len(i[1])) for i in goldalign]):
        #print('precision (for ' + str(gapdist) + ' alignments)')
        #testalign = []
        #for i in self.multialign:
          #if (len(i[0][0]),len(i[0][1])) == gapdist:
            #testalign.append(i)
        #self.precision(goldalign,testalign)

      for aligntype in set([i[1] for i in self.multialign]):
        testalign = []
        for i in self.multialign:
          if i[1] == aligntype:
            testalign.append(i)
        print('precision for alignment type ' + str(aligntype) + ' ( ' + str(len(testalign)) + ' alignment pairs)')
        self.precision(goldalign,testalign)

      print('\ntotal precision:'),
      print(str(len(self.multialign)) + ' alignment pairs found')
      (tpstrict,fpstrict,tplax,fplax) = self.precision(goldalign,self.multialign)
      results['precision'] = (tpstrict,fpstrict,tplax,fplax)

      return results


    def precision(self,goldalign,testalign):
      
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
          y = 0
          for srclist,targetlist in goldalign:
            for s in src:
              if y==1:
                break   
              for t in target:
                if y==1:
                  break                   
                if s in srclist and t in targetlist:
                  fpstrict +=1
                  tplax +=1
                  y=1
                  #print('lax match: '),
                  #print('test ' + str((src,target)) + '\t gold ' + str((srclist,targetlist)))
                  break
          if y == 0:
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


    def recall(self,aligntype,goldalign,testalign):
      
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
            y = 0
            for src,target in testalign:
              for s in src:
                if y==1:
                  break                
                for t in target:
                  if y==1:
                    break
                  if s in srclist and t in targetlist:
                    tplax +=1
                    fnstrict+=1
                    y=1
                    #print('lax match: '),
                    #print('test ' + str((src,target)) + '\t gold ' + str((srclist,targetlist)))
                    break
            if y == 0:
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


    def finalevaluation(self,results):
      recall = [0,0,0,0]
      precision = [0,0,0,0]
      for i,k in results.items():
        #print(i)
        for m,j in enumerate(recall):
          recall[m] = j+ k['recall'][m]
        for m,j in enumerate(precision):
          precision[m] = j+ k['precision'][m]

      pstrict = (precision[0]/float(precision[0]+precision[1]))
      plax =(precision[2]/float(precision[2]+precision[3]))
      rstrict= (recall[0]/float(recall[0]+recall[1]))
      rlax=(recall[2]/float(recall[2]+recall[3]))
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
      
      #myout = "%.2f & %.2f & %.2f & %.2f & %.2f & %.2f &" %(pstrict,rstrict,fstrict,plax,rlax,flax)
      #print(myout)
          

#Allows parallelizing of alignment
if multiprocessing_enabled:
  class AlignMultiprocessed(multiprocessing.Process,Aligner):

    def __init__(self,tasks,options,scores):
      multiprocessing.Process.__init__(self)
      self.options = options
      self.tasks = tasks
      self.scores = scores 
      self.bleualign = None
      self.scoredict = None

    def run(self):
      
      i,data = self.tasks.get()
      while i != None:

        log('reading in article ' + str(i) + ': ',1),
        sourcelist,targetlist,translist1,translist2 = data
        self.multialign = self.process(sourcelist,targetlist,translist1,translist2)
        self.scores[i] = (data,self.multialign,self.bleualign,self.scoredict)
        
        i,data = self.tasks.get()


if __name__ == '__main__':

    options = load_arguments()

    a = Aligner(options)
    a.mainloop()
