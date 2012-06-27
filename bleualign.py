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
from operator import itemgetter
import gale_church
import score as bleu
from utils import evaluate, finalevaluation


if sys.version_info >= (2,6):
  import multiprocessing
  multiprocessing_enabled = 1
  number_of_threads = 4
else:
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
#possible members are: bleu1to1, galechurch
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


def load_arguments(sysargv):
    try:
        opts, args = getopt.getopt(sysargv[1:], "def:ho:s:t:v:", ["factored", "filter=", "filterthreshold=", "filterlang", "printempty", "deveval","eval", "help", "galechurch", "output=", "source=", "target=", "srctotarget=", "targettosrc=", "verbosity="])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err)) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    options = {}
    options['srcfile'] = None
    options['targetfile'] = None
    options['output'] = None
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
            options['srcfile'] = os.path.join(sys.path[0],'eval','eval1989.de')
            options['targetfile'] = os.path.join(sys.path[0],'eval','eval1989.fr')
            options['eval'] = 1990
        elif o in ("-d", "--deveval"):
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
        elif o == "--printempty":
            options['printempty'] = True
        elif o in ("-v", "--verbosity"):
            global loglevel
            loglevel = int(a)
            options['loglevel'] = int(a)
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
    if options['targettosrc'] and not options['srctotarget']:
        print('\nWARNING: Only --targettosrc specified, but expecting at least one --srctotarget. Please swap source and target side.')
        sys.exit(2)

    return options


def log(msg,level=1):
  if level <= loglevel:
    print(msg)


def collect_article(src,srctotarget,target,targettosrc,options):

    EOF = False
    while not EOF:

        all_texts = []
        all_translations = []

        for text,translations in [(src,srctotarget),(target,targettosrc)]:
            textlist = []
            translist = [[] for i in translations]

            for line in text:

                if line.rstrip() == end_of_article_marker:
                    for f in translations:
                        f.readline()
                    break

                for i,f in enumerate(translations):
                    translist[i].append(f.readline().rstrip())

                if options['factored']:
                    rawline = ' '.join(word.split('|')[0] for word in line.split())
                    textlist.append(rawline,line.rstrip())
                else:
                    textlist.append(line.rstrip())
            else:
                EOF = True

            all_texts.append(textlist)
            all_translations.append(translist)

        sourcelist, targetlist = all_texts
        translist1, translist2 = all_translations
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
      self.src, self.target = None,None
      self.out1, self.out2, self.out_bad1, self.out_bad2 = None,None,None,None
      self.finalbleu = []
      self.srctotarget, self.targettosrc, self.sources_out,self.targets_out = [],[],[],[]
      self.options = options
      self.bleualign = []
      
      if options['srcfile']:
        self.src = open(options['srcfile'],'rU')
      if options['targetfile']:
        self.target = open(options['targetfile'],'rU')

      if options['output-src']:
        self.out1 = open(options['output-src'],'w')
      elif options['output']:
        self.out1 = open(options['output'] + '-s','w')
      if options['output-target']:
        self.out2 = open(options['output-target'],'w')
      elif options['output']:
        self.out2 = open(options['output'] + '-t','w')
      if options['output'] and options['filter']:
        self.out_bad1 = open(options['output'] + '-bad-s','w')
        self.out_bad2 = open(options['output'] + '-bad-t','w')

      if options['srctotarget']:
        for f in options['srctotarget']:
          self.srctotarget.append(open(f,'rU'))
      if options['targettosrc']:
        for f in options['targettosrc']:
          self.targettosrc.append(open(f,'rU'))


    #takes care of multiprocessing; calls process() function for each article
    def mainloop(self):
      
      results = {}

      if multiprocessing_enabled:
        tasks = multiprocessing.Queue(number_of_threads+1)

        manager = multiprocessing.Manager()
        scores = manager.dict()
        num_tasks = manager.Value('i',1)
        scorers = [AlignMultiprocessed(tasks,self.options,scores)  for i in range(number_of_threads)]

        for p in scorers:
          p.start()

        #this function produces the alignment tasks for the consumers in scorers
        producer = multiprocessing.Process(target=tasks_producer,args=(tasks,num_tasks,(self.src,self.srctotarget,self.target,self.targettosrc,self.options)))
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

            #normal case: translation from source to target exists
            if translist1:
                translist = translist1[0]

            #no translation provided. we copy source sentences for further processing
            else:
                if self.options['factored']:
                    translist = [item[0] for item in sourcelist]
                else:
                    translist = sourcelist

            self.printout(sourcelist, translist, targetlist)

            if self.options['eval']:
                print('evaluation ' + str(i))
                results[i] = evaluate(i, self.options,self.multialign)
            
            del(scores[i])
            i += 1

      else:
        for i,(sourcelist,targetlist,translist1,translist2) in enumerate(collect_article(self.src,self.srctotarget,self.target,self.targettosrc,self.options)):
          log('reading in article ' + str(i) + ': ',1),

          self.multialign = self.process(sourcelist,targetlist,translist1,translist2)
          if translist1:
              translist = translist1[0]
          else:
              if self.options['factored']:
                translist = [item[0] for item in sourcelist]
              else:
                translist = sourcelist
          self.printout(sourcelist, translist, targetlist)
          if self.options['eval']:
            print('evaluation ' + str(i))
            results[i] = evaluate(i, self.options, self.multialign)

      if self.options['eval']:
        finalevaluation(results)

      if self.options['filter']:
        self.write_filtered()


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

      if self.options['factored']:
          raw_sourcelist = [item[0] for item in sourcelist]
          raw_targetlist = [item[0] for item in targetlist]
      else:
          raw_sourcelist = sourcelist
          raw_targetlist = targetlist

      for i,translist in enumerate(translist1):
        log("computing alignment between srctotarget (file " + str(i) + ") and target text",1)
        phase1.append(self.align(translist, raw_targetlist))

      for i,translist in enumerate(translist2):
        log("computing alignment between targettosrc (file " + str(i) + ") and source text",1)
        phase2.append(self.align(translist, raw_sourcelist))

      if not (translist1 or translist2):
        if not self.options['galechurch']:
            log("""ERROR: no translation available:
BLEU scores can be computed between the source and target text, but this is not the intended usage of Bleualign and may result in poor performance!
If you're *really* sure that this is what you want, find this error message and remove the exit() statement on the next line""",1)
            exit()
        else:
            phase1 = [self.align(raw_sourcelist, raw_targetlist)]

      if len(phase1) > 1:
        log("intersecting all srctotarget alignments",1)
        phase1 = sorted(set(phase1[0]).intersection(*[set(x) for x in phase1[1:]]))
      elif phase1:
        phase1 = phase1[0]

      if len(phase2) > 1:
        log("intersecting all targettosrc alignments",1)
        phase2b = sorted(set(phase2[0]).intersection(set(x) for x in phase2[1:]))
      elif phase2:
        phase2 = phase2[0]

      if phase1 and phase2:
        log("intersecting both directions",1)
        phase3 = []
        phase2mirror = [(j,k) for ((k,j),t) in phase2]
        for pair,t in phase1:
          if pair in phase2mirror:
            phase3.append((pair,'INTERSECT: ' + t + ' - ' + phase2[phase2mirror.index(pair)][1]))
        multialign = phase3
        
      elif phase1:
        multialign = phase1
        
      elif phase2:
        multialign = [((j,k),t) for ((k,j),t) in phase2]

      return multialign


    #Compute alignment for one article and one automatic translation.
    def align(self, translist, targetlist):

      if self.options["galechurch"]:
        self.multialign,self.bleualign,self.scoredict = [],[],{}
        translist = [item for item in enumerate(translist)]
        targetlist =  [item for item in enumerate(targetlist)]
        churchaligns = self.gale_church(translist,targetlist)
        for src,target in churchaligns:
          self.addtoAlignments((src,target),'GALECHURCH')
        return self.multialign

      else:
        log('Evaluating sentences with bleu',1)
        self.scoredict = self.eval_sents(translist,targetlist)
        log('finished',1)
        log('searching for longest path of good alignments',1)
        self.pathfinder(translist, targetlist)
        log('finished',1)
        log(time.asctime(),2)
        log('filling gaps',1)
        self.gapfinder(translist, targetlist)
        log('finished',1)
        log(time.asctime(),2)
        return self.multialign


   #use this if you want to implement your own similarity score
    def eval_sents_dummy(self,translist,targetlist):
      scoredict = {}
      
      for testID,testSent in enumerate(translist):
        scores = []
        
        for refID,refSent in enumerate(targetlist):
          score = 100-abs(len(testSent)-len(refSent)) #replace this with your own similarity score
          if score > 0:
            scores.append((score,refID,score))
        scoredict[testID] = sorted(scores,key=itemgetter(0),reverse=True)[:maxalternatives]
            
      return scoredict


    # given list of test sentences and list of reference sentences, calculate bleu scores
    #if you want to replace bleu with your own similarity measure, use eval_sents_dummy
    def eval_sents(self,translist,targetlist):
      
      scoredict = {}
      cooked_test = {}
      cooked_test2 = {}
      cooktarget =  [(items[0],bleu.cook_refs([items[1]],bleu_ngrams)) for items in enumerate(targetlist)]
      cooktarget = [(refID,(reflens, refmaxcounts, set(refmaxcounts))) for (refID,(reflens, refmaxcounts)) in cooktarget]


      for testID,testSent in enumerate(translist):
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


    #follow the backpointers in score matrix to extract best path of 1-to-1 alignments
    def extract_best_path(self,matrix):

        i = len(matrix)-1
        j = len(matrix[i])-1
        pointer = ''
        best_path = []

        while i >= 0 and j >= 0 and pointer != '-':
            score, pointer = matrix[i][j]
            if pointer == '^':
                i -= 1
            elif pointer == '<':
                j -= 1
            elif pointer == 'match':
                best_path.append((i,j))
                i -= 1
                j -= 1

        best_path.reverse()
        return best_path


    #dynamic programming search for best path of alignments (maximal score)
    def pathfinder(self, translist, targetlist):

        matrix = [[(0,'-') for column in targetlist] for row in translist]

        for i, s_sent in enumerate(translist):
            alignments = dict([(target, score) for (score, target, correct) in self.scoredict[i]])

            for j, t_sent in enumerate(targetlist):
                best_score, best_pointer = 0,'-'

                if i:
                    score, pointer = matrix[i-1][j]
                    if score > best_score:
                        best_score = score
                        best_pointer = '^'

                if j:
                    score, pointer = matrix[i][j-1]
                    if score > best_score:
                        best_score = score
                        best_pointer = '<'

                if j in alignments:
                    score = alignments[j]

                    if i and j:
                        score += matrix[i-1][j-1][0]

                    if score > best_score:
                        best_score = score
                        best_pointer = 'match'

                matrix[i][j] = (best_score, best_pointer)

        self.bleualign = self.extract_best_path(matrix)


    #find unaligned sentences and create work packets for gapfiller()
    #gapfiller() takes two sentence pairs and all unaligned sentences in between as arguments; gapfinder() extracts these.
    def gapfinder(self, translist, targetlist):
      
      self.multialign = []
      
      #find gaps: lastpair is considered pre-gap, pair is post-gap
      lastpair = ((),())
      src, target = None, None
      for src,target in self.bleualign:

        oldsrc, oldtarget = lastpair
        #in first iteration, gap will start at 0
        if not oldsrc:
            oldsrc = (-1,)
        if not oldtarget:
            oldtarget = (-1,)

        #identify gap sizes
        sourcegap = range(oldsrc[-1]+1,src)
        targetgap = range(oldtarget[-1]+1,target)

        if targetgap or sourcegap:
          lastpair = self.gapfiller(sourcegap, targetgap, lastpair, ((src,),(target,)), translist, targetlist)
        else:
          self.addtoAlignments(lastpair)
          lastpair = ((src,),(target,))

      #if self.bleualign is empty, gap will start at 0
      if not src:
          src = -1
      if not target:
          target = -1

      #search for gap after last alignment pair
      sourcegap = range(src+1, len(translist))
      targetgap = range(target+1, len(targetlist))

      if targetgap or sourcegap:
        lastpair = self.gapfiller(sourcegap, targetgap, lastpair, ((),()), translist, targetlist)
      
      self.addtoAlignments(lastpair)


    #apply heuristics to align all sentences that remain unaligned after finding best path of 1-to-1 alignments
    #heuristics include bleu-based 1-to-n alignment and length-based alignment
    def gapfiller(self, sourcegap, targetgap, pregap, postgap, translist, targetlist):

      evalsrc = []
      evaltarget = []

      #compile list of sentences in gap that will be considered for BLEU comparison
      if Nto1 > 1 or "bleu1to1" in gapfillheuristics:

        #concatenate all sentences in pregap alignment pair
        tmpstr =  ''.join([translist[i] for i in pregap[0]])
        evalsrc.append((pregap[0],tmpstr))

        #concatenate all sentences in pregap alignment pair
        tmpstr =  ''.join([targetlist[i] for i in pregap[1]])
        evaltarget.append((pregap[1],tmpstr))
        
        #search will be pruned to this window
        if "bleu1to1" in gapfillheuristics:
          window = 10 + Nto1
        else:
          window = Nto1
        
        for src in [j for i,j in enumerate(sourcegap) if (i < window or len(sourcegap)-i <= window)]:
          Sent = translist[src]
          evalsrc.append(((src,),Sent))
        
        for target in [j for i,j in enumerate(targetgap) if (i < window or len(targetgap)-i <= window)]:
          Sent = targetlist[target]
          evaltarget.append(((target,),Sent))
        
        #concatenate all sentences in postgap alignment pair
        tmpstr =  ''.join([translist[i] for i in postgap[0]])
        evalsrc.append((postgap[0],tmpstr))
        
        #concatenate all sentences in postgap alignment pair
        tmpstr =  ''.join([targetlist[i] for i in postgap[1]])
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
        
        evalsrc_raw = [item[1] for item in evalsrc]
        evaltarget_raw = [item[1] for item in evaltarget]
        
        scoredict_raw = self.eval_sents(evalsrc_raw,evaltarget_raw)
        
        scoredict = {}
        for src,value in scoredict_raw.items():
            src = evalsrc[src][0]
            if value:
                newlist = []
                for item in value:
                    score,target,score2 = item
                    target = evaltarget[target][0]
                    newlist.append((score,target,score2))
                scoredict[src] = newlist
            else:
                scoredict[src] = []

      while sourcegap or targetgap:
        pregapsrc,pregaptarget = pregap
        postgapsrc,postgaptarget = postgap
          
        if sourcegap and Nto1 > 1:
          
          #try if concatenating source sentences together improves bleu score (beginning of gap)
          if pregapsrc:
            oldscore,oldtarget,oldcorrect = scoredict[pregapsrc][0]
            combinedID = tuple(list(pregapsrc)+[sourcegap[0]])
            if combinedID in scoredict:
                newscore,newtarget,newcorrect = scoredict[combinedID][0]

                if newscore > oldscore and newcorrect > oldcorrect and newtarget == pregaptarget:
                    #print('\nsource side: ' + str(combinedID) + ' better than ' + str(pregapsrc))
                    pregap = (combinedID,pregaptarget)
                    sourcegap.pop(0)
                    continue
            
          #try if concatenating source sentences together improves bleu score (end of gap)
          if postgapsrc:
            oldscore,oldtarget,oldcorrect = scoredict[postgapsrc][0]
            combinedID = tuple([sourcegap[-1]] + list(postgapsrc))
            if combinedID in scoredict:
                newscore,newtarget, newcorrect = scoredict[combinedID][0]
                if newscore > oldscore  and newcorrect > oldcorrect and newtarget == postgaptarget:
                    #print('\nsource side: ' + str(combinedID) + ' better than ' + str(postgapsrc))
                    postgap = (combinedID,postgaptarget)
                    sourcegap.pop()
                    continue

        if targetgap  and Nto1 > 1:
          
          #try if concatenating target sentences together improves bleu score (beginning of gap)
          if pregapsrc:
            newscore,newtarget,newcorrect = scoredict[pregapsrc][0]
            if newtarget != pregaptarget:
                #print('\ntarget side: ' + str(newtarget) + ' better than ' + str(pregaptarget))
                pregap = (pregapsrc,newtarget)
                for i in newtarget:
                  if i in targetgap:
                    del(targetgap[targetgap.index(i)])
                continue

          #try if concatenating target sentences together improves bleu score (end of gap)
          if postgapsrc:
            newscore,newtarget,newcorrect = scoredict[postgapsrc][0]
            if newtarget != postgaptarget:
                #print('\ntarget side: ' + str(newtarget) + ' better than ' + str(postgaptarget))
                postgap = (postgapsrc,newtarget)
                for i in newtarget:
                  if i in targetgap:
                    del(targetgap[targetgap.index(i)])
                continue
        
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

          #Alternative approach: use Gale & Church.
          if "galechurch" in gapfillheuristics and (max(len(targetgap),len(sourcegap))<4 or max(len(targetgap),len(sourcegap))/min(len(targetgap),len(sourcegap)) < 2):
            tempsrcgap = []
            for src in sourcegap:
              tempsrcgap.append((src,translist[src]))
            
            temptargetgap = []
            for target in targetgap:
              temptargetgap.append((target,targetlist[target]))

              
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


    def print_alignment_statistics(self, source_len, target_len):
        multialignsrccount = sum([len(i[0][0]) for i in self.multialign])
        multialigntargetcount = sum([len(i[0][1]) for i in self.multialign])

        log("Results of BLEU 1-to-1 alignment",2)
        if loglevel >= 2:
            bleualignsrc = list(map(itemgetter(0),self.bleualign))
            for sourceid in range(len(sourcelist)):
                if sourceid in bleualignsrc:
                    print('\033[92m' + str(sourceid) + ": "),
                    print(str(self.bleualign[bleualignsrc.index(sourceid)][1]) + '\033[1;m')
                else:
                    print('\033[1;31m'+str(sourceid) + ": unaligned. best cand "),
                    bestcand = self.scoredict.get(sourceid,[])
                    if bestcand:
                        bestcand = bestcand[0][1]
                    print(str(bestcand)+'\033[1;m')

        if source_len and target_len:
            log("\n" + str(len(self.bleualign)) + ' out of ' + str(source_len) + ' source sentences aligned by BLEU ' + str(100*len(self.bleualign)/float(source_len)) + '%',2)
            log("after gap filling, " + str(multialignsrccount) + ' out of '+ str(source_len) + ' source sentences aligned ' + str(100*multialignsrccount/float(source_len)) + '%',2)
            log("after gap filling, " + str(multialigntargetcount) + ' out of '+ str(target_len) + ' target sentences aligned ' + str(100*multialigntargetcount/float(source_len)) + '%',2)


    #print out some debugging info, and print output to file
    def printout(self, sourcelist, translist, targetlist):

      self.print_alignment_statistics(len(sourcelist), len(targetlist))

      sources = []
      translations = []
      targets = []
      sources_factored = []
      targets_factored = []
      self.multialign = sorted(self.multialign,key=itemgetter(0))
      sentscores = {}
      lastsrc,lasttarget = 0,0
      for j,(src,target) in enumerate([i[0] for i in self.multialign]):

        if self.options['printempty']:
            if src[0] != lastsrc + 1:
                sources.extend([sourcelist[ID] for ID in range(lastsrc+1,src[0])])
                targets.extend(['' for ID in range(lastsrc+1,src[0])])
                translations.extend(['' for ID in range(lastsrc+1,src[0])])

            if target[0] != lasttarget + 1:
                sources.extend(['' for ID in range(lasttarget+1,target[0])])
                targets.extend([targetlist[ID] for ID in range(lasttarget+1,target[0])])
                translations.extend(['' for ID in range(lasttarget+1,target[0])])

        sources.append(' '.join([sourcelist[ID] for ID in src]))
        targets.append(' '.join([targetlist[ID] for ID in target]))
        translations.append(' '.join([translist[ID] for ID in src]))

        lastsrc = src[-1]
        lasttarget = target[-1]

        if self.options['factored']:
          sources_factored.append(' '.join([sourcelist[ID][1] for ID in src]))
          targets_factored.append(' '.join([targetlist[ID][1] for ID in target]))

        if self.options['filter'] == 'sentences':
            self.check_sentence_pair(options, sources[-1], translations[-1], targets[-1], sentscores)

      if self.options['filter'] == 'sentences':
        self.filter_sentence_pairs(sentscores)

      if self.options['filter'] == 'articles':
        self.filter_article_pairs(options, sources, translations, targets, sources_factored, targets_factored)

      log("\nfinished with article",1)
      log("\n====================\n",1)

      if self.out1 and self.out2 and not self.options['filter']:
        if self.options['factored']:
            self.out1.writelines(sources_factored)
            self.out2.writelines(targets_factored)
        else:
            self.out1.writelines(sources)
            self.out2.writelines(targets)


    #get BLEU score of sentence pair (for filtering)
    def check_sentence_pair(self, options, src, trans, target, sentscores):

          sentscore = self.score_article([trans],[target])
          sentscore2 = self.score_article([src],[target])
          if sentscore2 > sentscore and options['filterlang']:
            if options['factored']:
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


    # get BLEU score for article pair
    def score_article(self,test,ref):
      refs = [bleu.cook_refs([refSent],bleu_ngrams) for refSent in ref]
      testcook = []

      for i,line in enumerate(test):
        testcook.append(bleu.cook_test(line,refs[i],bleu_ngrams))

      score = bleu.score_cooked(testcook,bleu_ngrams)
      return score


    # store BLEU score for each sentence pair (used for filtering at the very end)
    def filter_sentence_pairs(self, sentscores):
        before = 0
        for j,(src,target) in enumerate([i[0] for i in self.multialign]):
            if j in sentscores: # false if sentence pair has been filtered out by language filter
                confidence = sentscores[j]
                self.finalbleu.append((confidence,sentscores.get(j),before,before+1))
                before += 1
                self.sources_out.append(sources[j])
                self.targets_out.append(targets[j])


    # store BLEU score for each article pair (used for filtering at the very end)
    def filter_article_pairs(self, options, sources, translations, targets, sources_factored, targets_factored):
        articlescore = self.score_article(translations,targets)
        articlescore2 = self.score_article(sources,targets)

        log('\nBLEU score for article: ' + str(articlescore) + ' / ' + str(articlescore2),1)

        if articlescore2 > articlescore and options['filterlang']:
            if self.options['factored']:
                sources,targets = sources_factored,targets_factored
            for i,line in enumerate(sources):
                self.out_bad1.write(line + '\n')
                self.out_bad2.write(targets[i] + '\n')
            else:
                articlescorex = self.score_article(targets,translations)
                if articlescore > 0:
                    articlescore = (articlescore*articlescorex*2)/(articlescore+articlescorex)
                after = before + len(self.multialign)
                self.finalbleu.append((articlescore,articlescore2,before,after))
                before = after

            if self.options['factored']:
                sources,targets = sources_factored,targets_factored

            self.sources_out += sources
            self.targets_out += targets


    #filter bad sentence pairs / article pairs
    def write_filtered(self):
      
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


#Allows parallelizing of alignment
if multiprocessing_enabled:
  class AlignMultiprocessed(multiprocessing.Process,Aligner):

    def __init__(self,tasks,options,scores):
      multiprocessing.Process.__init__(self)
      self.options = options
      self.tasks = tasks
      self.scores = scores 
      self.bleualign = []
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

    options = load_arguments(sys.argv)

    a = Aligner(options)
    a.mainloop()
