#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2010 University of Zürich
# Author: Rico Sennrich <sennrich@cl.uzh.ch>
# For licensing information, see LICENSE

from __future__ import division,print_function
import sys
import time
import math
from operator import itemgetter
from bleualign.gale_church import align_texts
import bleualign.score as bleu
from bleualign.utils import evaluate, finalevaluation
import io


if sys.version_info >= (2,6):
  import multiprocessing
  multiprocessing_enabled = 1
  number_of_threads = 4
else:
  multiprocessing_enabled = 0


def collect_article(src,srctotarget,target,targettosrc,options):

    EOF = False
    while not EOF:

        all_texts = []
        all_translations = []

        for text,translations in [(src,srctotarget),(target,targettosrc)]:
            textlist = []
            translist = [[] for i in translations]

            for line in text:

                if line.rstrip() == options['end_of_article_marker']:
                    for f in translations:
                        f.readline()
                    break

                for i,f in enumerate(translations):
                    translist[i].append(f.readline().rstrip())

                if options['factored']:
                    rawline = ' '.join(word.split('|')[0] for word in line.split())
                    textlist.append((rawline,line.rstrip()))
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
    default_options = {
        #source and target files needed by Aligner
        #they can be filenames, arrays of strings or io objects.
        'srcfile':None, 'targetfile': None,

        #the format of srcfile and targetfile
        #False for normal text, True for 'text | other information', seprating by '|'
        'factored': False,

        #translations of srcfile and targetfile, not influenced by 'factored'
        #they can be filenames, arrays of strings or io objects, too.
        'srctotarget': [], 'targettosrc': [],
        #run aligner without srctotarget and targettosrc
        'no_translation_override':False,
        
        #only consider target sentences for bleu-based alignment that are among top N alternatives for a given source sentence
        'maxalternatives':3,
        
        #bleu scoring algorithm works with 4-grams by default. We got better results when using 2-grams (since there are less 0 scores then)
        'bleu_ngrams' : 2,

        #consider N to 1 (and 1 to N) alignment in gapfilling (complexity is size_of_gap*value^2, so don't turn this unnecessarily high)
        #also, there are potential precision issues.
        #set to 1 to disable bleu-based 1 to N alignments and let gale & church fill the gaps
        'Nto1' : 2,
        
        #do only gale-church, no bleualign
        'galechurch': None,

        #gapfillheuristics: what to do with sentences that aren't aligned one-to-one by the first BLEU pass, nor have a 1 to N alignment validated by BLEU?
        #possible members are: bleu1to1, galechurch
        #what they do is commented in the source code
        'gapfillheuristics' : ["bleu1to1","galechurch"],

        #defines string that identifies hard boundaries (articles, chapters etc.)
        #string needs to be on a line of its own (see examples in eval directory)
        #must be reliable (article i in the source text needs to correspond to article i in the target text)
        'end_of_article_marker' : ".EOA",

        #filtering good and bad alignemts by bleuscore
        #filter has sentences or articles type
        #filterthreshold means choices the higher percentage of alignment
        #set filterlang True, whose when you want to filter alignemts which src is similar to target than translation
        'filter': None, 'filterthreshold': 90, 'filterlang': None,
        
        #it will print unalignemt pair(zero to one or one to zero pair)
        'printempty': False,
        
        #setting output for four output filenames, it will add suffixes automatically
        #or passing filenames or io object for them in respectly.
        #if not passing anything or assigning None, they will use StringIO to save results.
        'output': None,
        'output-src': None, 'output-target': None,
        'output-src-bad': None, 'output-target-bad': None,
        #the best alignment of corpus for evaluation
        'eval': None,
        #defines amount of debugging output.
        'verbosity': 1, 'log_to':sys.stdout,
        }
    def __init__(self,options):
      self.src, self.target = None,None
      self.srctotarget, self.targettosrc= [],[]
      self.out1, self.out2, self.out_bad1, self.out_bad2 = None,None,None,None
      self.sources_out,self.targets_out = [],[]
      self.finalbleu = []
      self.bleualign = []
      self.close_src, self.close_target = False, False
      self.close_srctotarget, self.close_targettosrc = [], []
      self.close_out1, self.close_out2 = False, False
      self.close_out_bad1, self.close_out_bad2 = False, False 
      self.options = self.default_options.copy()
      self.options.update(options)
      
      if not self.options['srcfile']:
        raise ValueError('Source file not specified.')
      if not self.options['targetfile']:
        raise ValueError('Target file not specified.')
      if not self.options['srctotarget'] and not self.options['targettosrc']\
            and not self.options['no_translation_override']:
        raise ValueError("ERROR: no translation available: BLEU scores can be computed between the source and target text, but this is not the intended usage of Bleualign and may result in poor performance! If you're *really* sure that this is what you want, set 'galechurch' for the options.")

      self.src, self.close_src = \
            self._inputObjectFromParameter(self.options['srcfile'])
      self.target, self.close_target = \
            self._inputObjectFromParameter(self.options['targetfile'])

      for f in self.options['srctotarget']:
            obj, close_obj = \
                self._inputObjectFromParameter(f)
            self.srctotarget.append(obj)
            self.close_srctotarget.append(close_obj)
      for f in self.options['targettosrc']:
            obj, close_obj = \
                self._inputObjectFromParameter(f)
            self.targettosrc.append(obj)
            self.close_targettosrc.append(close_obj)

      self.out1,self.close_out1=self._outputObjectFromParameter(
            self.options['output-src'], self.options['output'], '-s')
      self.out2,self.close_out2=self._outputObjectFromParameter(
            self.options['output-target'], self.options['output'], '-t')

      if self.options['filter']:
        self.out_bad1,self.close_out_bad1=self._outputObjectFromParameter(
            self.options['output-src-bad'], self.options['output'], '-bad-s')
        self.out_bad2,self.close_out_bad2=self._outputObjectFromParameter(
            self.options['output-target-bad'], self.options['output'], '-bad-t')

    # for passing by string array
    def _stringArray2stringIo(self, stringArray):
        return io.StringIO('\n'.join([line.rstrip() for line in stringArray]))

    # parameter may be filename, IO object or string array
    def _inputObjectFromParameter(self, parameter):
        try:
            inputObject = io.open(parameter, 'r')
            close_object = True
        except:
            if isinstance(parameter, io.TextIOBase):
                inputObject = parameter
            else:
                inputObject = self._stringArray2stringIo(parameter)
            close_object = False
        return inputObject, close_object
 
    # parameter may be filename, IO object or string array
    def _outputObjectFromParameter(self, parameter, filename, suffix):
        close_object = False
        if parameter:
            try:
                outputObject = io.open(parameter, 'w')
                close_object = True
            except:
                outputObject = parameter
        elif filename:
            outputObject = io.open(filename + suffix, 'w')
        else:
            outputObject = io.StringIO()
        return outputObject, close_object

    #takes care of multiprocessing; calls process() function for each article
    def mainloop(self):
      
      results = {}

      if multiprocessing_enabled:
        tasks = multiprocessing.Queue(number_of_threads+1)

        manager = multiprocessing.Manager()
        scores = manager.dict()
        num_tasks = manager.Value('i',1)
        scorers = [AlignMultiprocessed(tasks,self.options,scores,self.log)  for i in range(number_of_threads)]

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
                    for p in scorers:
                        if p.exitcode == 1:
                            for p in scorers:
                                p.terminate()
                            producer.terminate()
                            raise RuntimeError("Multiprocessing error")
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
                self.log('evaluation ' + str(i))
                results[i] = evaluate(self.options,self.multialign,self.options['eval'][i],self.log)
            
            del(scores[i])
            i += 1

      else:
        for i,(sourcelist,targetlist,translist1,translist2) in enumerate(collect_article(self.src,self.srctotarget,self.target,self.targettosrc,self.options)):
          self.log('reading in article ' + str(i) + ': ',1)

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
            self.log('evaluation ' + str(i))
            results[i] = evaluate(self.options, self.multialign,self.options['eval'][i],self.log)

      if self.out1:
        self.out1.flush()
      if self.out2:
        self.out2.flush()

      if self.options['eval']:
        finalevaluation(results, self.log)

      if self.options['filter']:
        self.write_filtered()

      self.close_file_streams()

      return self.out1,self.out2

    #results of alignment or good aligment if filtering
    def results(self):
        return self.out1,self.out2
       
    #bad aligment for filtering. Otherwise, None
    def results_bad(self):
        return self.out_bad1,self.out_bad2

    #Start different alignment runs depending on which and how many translations are sent to program; intersect results.
    def process(self,sourcelist,targetlist,translist1,translist2):
        
      multialign = []
        
      phase1 = []
      phase2 = []

      #do nothing if last line in file is .EOA or file is empty.
      if not targetlist or not sourcelist:
        self.log('WARNING: article is empty. Skipping.',0)
        return []

      self.log('processing',1)

      if self.options['factored']:
          raw_sourcelist = [item[0] for item in sourcelist]
          raw_targetlist = [item[0] for item in targetlist]
      else:
          raw_sourcelist = sourcelist
          raw_targetlist = targetlist

      for i,translist in enumerate(translist1):
        self.log("computing alignment between srctotarget (file " + str(i) + ") and target text",1)
        phase1.append(self.align(translist, raw_targetlist))

      for i,translist in enumerate(translist2):
        self.log("computing alignment between targettosrc (file " + str(i) + ") and source text",1)
        phase2.append(self.align(translist, raw_sourcelist))

      if not (translist1 or translist2):
        if self.options['no_translation_override'] or self.options['galechurch']:
            phase1 = [self.align(raw_sourcelist, raw_targetlist)]
        else:
            self.log("ERROR: no translation available", 1)
            if multiprocessing_enabled:
                sys.exit(1)
            else:
                raise RuntimeError("ERROR: no translation available")

      if len(phase1) > 1:
        self.log("intersecting all srctotarget alignments",1)
        phase1 = sorted(set(phase1[0]).intersection(*[set(x) for x in phase1[1:]]))
      elif phase1:
        phase1 = phase1[0]

      if len(phase2) > 1:
        self.log("intersecting all targettosrc alignments",1)
        phase2 = sorted(set(phase2[0]).intersection(*[set(x) for x in phase2[1:]]))
      elif phase2:
        phase2 = phase2[0]

      if phase1 and phase2:
        self.log("intersecting both directions",1)
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
        self.log('Evaluating sentences with bleu',1)
        self.scoredict = self.eval_sents(translist,targetlist)
        self.log('finished',1)
        self.log('searching for longest path of good alignments',1)
        self.pathfinder(translist, targetlist)
        self.log('finished',1)
        self.log(time.asctime(),2)
        self.log('filling gaps',1)
        self.gapfinder(translist, targetlist)
        self.log('finished',1)
        self.log(time.asctime(),2)
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
        scoredict[testID] = sorted(scores,key=itemgetter(0),reverse=True)[:self.options['maxalternatives']]
            
      return scoredict


    # given list of test sentences and list of reference sentences, calculate bleu scores
    #if you want to replace bleu with your own similarity measure, use eval_sents_dummy
    def eval_sents(self,translist,targetlist):
      
      scoredict = {}
      cooked_test = {}
      cooked_test2 = {}
      cooktarget =  [(items[0],bleu.cook_refs([items[1]],self.options['bleu_ngrams'])) for items in enumerate(targetlist)]
      cooktarget = [(refID,(reflens, refmaxcounts, set(refmaxcounts))) for (refID,(reflens, refmaxcounts)) in cooktarget]


      for testID,testSent in enumerate(translist):
        scorelist = []


        #copied over from bleu.py to minimize redundancy
        test_normalized = bleu.normalize(testSent)
        cooked_test["testlen"] = len(test_normalized)
        cooked_test["guess"] = [max(len(test_normalized)-k+1,0) for k in range(1,self.options['bleu_ngrams']+1)]
        counts = bleu.count_ngrams(test_normalized, self.options['bleu_ngrams'])
        
        #separate by n-gram length. if we have no matching bigrams, we don't have to compare unigrams
        ngrams_sorted = dict([(x,set()) for x in range(self.options['bleu_ngrams'])])
        for ngram in counts:
            ngrams_sorted[len(ngram)-1].add(ngram)
            

        for (refID,(reflens, refmaxcounts, refset)) in cooktarget:
            
          ngrams_filtered = ngrams_sorted[self.options['bleu_ngrams']-1].intersection(refset)
        
          if ngrams_filtered:
            cooked_test["reflen"] = reflens[0]
            cooked_test['correct'] = [0]*self.options['bleu_ngrams']
            for ngram in ngrams_filtered:
              cooked_test["correct"][self.options['bleu_ngrams']-1] += min(refmaxcounts[ngram], counts[ngram])
            
            for order in range(self.options['bleu_ngrams']-1):
                for ngram in ngrams_sorted[order].intersection(refset):
                    cooked_test["correct"][order] += min(refmaxcounts[ngram], counts[ngram])

            #copied over from bleu.py to minimize redundancy
            logbleu = 0.0
            for k in range(self.options['bleu_ngrams']):
                logbleu += math.log(cooked_test['correct'][k])-math.log(cooked_test['guess'][k])
            logbleu /= self.options['bleu_ngrams']
            logbleu += min(0,1-float(cooked_test['reflen'])/cooked_test['testlen'])
            score = math.exp(logbleu)
            
            if score > 0:
                #calculate bleu score in reverse direction
                cooked_test2["guess"] = [max(cooked_test['reflen']-k+1,0) for k in range(1,self.options['bleu_ngrams']+1)]
                logbleu = 0.0
                for k in range(self.options['bleu_ngrams']):
                    logbleu += math.log(cooked_test['correct'][k])-math.log(cooked_test2['guess'][k])
                logbleu /= self.options['bleu_ngrams']
                logbleu += min(0,1-float(cooked_test['testlen'])/cooked_test['reflen'])
                score2 = math.exp(logbleu)
                
                meanscore = (2*score*score2)/(score+score2)
                scorelist.append((meanscore,refID,cooked_test['correct']))
              
        scoredict[testID] = sorted(scorelist,key=itemgetter(0),reverse=True)[:self.options['maxalternatives']]
        
      return scoredict


    #follow the backpointers in score matrix to extract best path of 1-to-1 alignments
    def extract_best_path(self,pointers):

        i = len(pointers)-1
        j = len(pointers[0])-1
        pointer = ''
        best_path = []

        while i >= 0 and j >= 0:
            pointer = pointers[i][j]
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

        # add an extra row/column to the matrix and start filling it from 1,1 (to avoid exceptions for first row/column)
        matrix = [[0 for column in range(len(targetlist)+1)] for row in range(len(translist)+1)]
        pointers = [['' for column in range(len(targetlist))] for row in range(len(translist))]

        for i in range(len(translist)):
            alignments = dict([(target, score) for (score, target, correct) in self.scoredict[i]])

            for j in range(len(targetlist)):

                best_score = matrix[i][j+1]
                best_pointer = '^'

                score = matrix[i+1][j]
                if score > best_score:
                    best_score = score
                    best_pointer = '<'

                if j in alignments:
                    score = alignments[j] + matrix[i][j]

                    if score > best_score:
                        best_score = score
                        best_pointer = 'match'

                matrix[i+1][j+1] = best_score
                pointers[i][j] = best_pointer

        self.bleualign = self.extract_best_path(pointers)


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
        sourcegap = list(range(oldsrc[-1]+1,src))
        targetgap = list(range(oldtarget[-1]+1,target))

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
      sourcegap = list(range(src+1, len(translist)))
      targetgap = list(range(target+1, len(targetlist)))

      if targetgap or sourcegap:
        lastpair = self.gapfiller(sourcegap, targetgap, lastpair, ((),()), translist, targetlist)
      
      self.addtoAlignments(lastpair)


    #apply heuristics to align all sentences that remain unaligned after finding best path of 1-to-1 alignments
    #heuristics include bleu-based 1-to-n alignment and length-based alignment
    def gapfiller(self, sourcegap, targetgap, pregap, postgap, translist, targetlist):

      evalsrc = []
      evaltarget = []

      #compile list of sentences in gap that will be considered for BLEU comparison
      if self.options['Nto1'] > 1 or "bleu1to1" in self.options['gapfillheuristics']:

        #concatenate all sentences in pregap alignment pair
        tmpstr =  ' '.join([translist[i] for i in pregap[0]])
        evalsrc.append((pregap[0],tmpstr))

        #concatenate all sentences in pregap alignment pair
        tmpstr =  ' '.join([targetlist[i] for i in pregap[1]])
        evaltarget.append((pregap[1],tmpstr))
        
        #search will be pruned to this window
        if "bleu1to1" in self.options['gapfillheuristics']:
          window = 10 + self.options['Nto1']
        else:
          window = self.options['Nto1']
        
        for src in [j for i,j in enumerate(sourcegap) if (i < window or len(sourcegap)-i <= window)]:
          Sent = translist[src]
          evalsrc.append(((src,),Sent))
        
        for target in [j for i,j in enumerate(targetgap) if (i < window or len(targetgap)-i <= window)]:
          Sent = targetlist[target]
          evaltarget.append(((target,),Sent))
        
        #concatenate all sentences in postgap alignment pair
        tmpstr =  ' '.join([translist[i] for i in postgap[0]])
        evalsrc.append((postgap[0],tmpstr))
        
        #concatenate all sentences in postgap alignment pair
        tmpstr =  ' '.join([targetlist[i] for i in postgap[1]])
        evaltarget.append((postgap[1],tmpstr))


        nSrc = {}
        for n in range(2,self.options['Nto1']+1):
          nSrc[n] = self.createNSents(evalsrc,n)
        for n in range(2,self.options['Nto1']+1):
          evalsrc += nSrc[n]

        nTar = {}
        for n in range(2,self.options['Nto1']+1):
          nTar[n] = self.createNSents(evaltarget,n)
        for n in range(2,self.options['Nto1']+1):
          evaltarget += nTar[n]
        
        evalsrc_raw = [item[1] for item in evalsrc]
        evaltarget_raw = [item[1] for item in evaltarget]
        
        scoredict_raw = self.eval_sents(evalsrc_raw,evaltarget_raw)
        
        scoredict = {}
        for src,value in list(scoredict_raw.items()):
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
          
        if sourcegap and self.options['Nto1'] > 1:
          
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

        if targetgap and self.options['Nto1'] > 1:
          
          #try if concatenating target sentences together improves bleu score (beginning of gap)
          if pregapsrc:
            newscore,newtarget,newcorrect = scoredict[pregapsrc][0]
            if newtarget != pregaptarget and newtarget != postgaptarget:
                #print('\ntarget side: ' + str(newtarget) + ' better than ' + str(pregaptarget))
                pregap = (pregapsrc,newtarget)
                for i in newtarget:
                  if i in targetgap:
                    del(targetgap[targetgap.index(i)])
                continue

          #try if concatenating target sentences together improves bleu score (end of gap)
          if postgapsrc:
            newscore,newtarget,newcorrect = scoredict[postgapsrc][0]
            if newtarget != postgaptarget and newtarget != pregaptarget:
                #print('\ntarget side: ' + str(newtarget) + ' better than ' + str(postgaptarget))
                postgap = (postgapsrc,newtarget)
                for i in newtarget:
                  if i in targetgap:
                    del(targetgap[targetgap.index(i)])
                continue
        
        #concatenation didn't help, and we still have possible one-to-one alignments
        if sourcegap and targetgap:

          #align first two sentences if BLEU validates this
          if "bleu1to1" in self.options['gapfillheuristics']:
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
          if "galechurch" in self.options['gapfillheuristics'] and (max(len(targetgap),len(sourcegap))<4 or max(len(targetgap),len(sourcegap))/min(len(targetgap),len(sourcegap)) < 2):
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
      pairs = sorted(list((align_texts(srclengths, targetlengths)[0])), key=itemgetter(0))

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

        self.log("Results of BLEU 1-to-1 alignment",2)
        if self.options['verbosity'] >= 2:
            bleualignsrc = list(map(itemgetter(0),self.bleualign))
            for sourceid in range(source_len):
                if sourceid in bleualignsrc:
                    self.log('\033[92m' + str(sourceid) + ": "
                        + str(self.bleualign[bleualignsrc.index(sourceid)][1]) + '\033[1;m')
                else:
                    bestcand = self.scoredict.get(sourceid,[])
                    if bestcand:
                        bestcand = bestcand[0][1]
                    self.log('\033[1;31m'+str(sourceid) + ": unaligned. best cand "
                        + str(bestcand)+'\033[1;m')

        if source_len and target_len:
            self.log("\n" + str(len(self.bleualign)) + ' out of ' + str(source_len) + ' source sentences aligned by BLEU ' + str(100*len(self.bleualign)/float(source_len)) + '%',2)
            self.log("after gap filling, " + str(multialignsrccount) + ' out of '+ str(source_len) + ' source sentences aligned ' + str(100*multialignsrccount/float(source_len)) + '%',2)
            self.log("after gap filling, " + str(multialigntargetcount) + ' out of '+ str(target_len) + ' target sentences aligned ' + str(100*multialigntargetcount/float(source_len)) + '%',2)


    #print out some debugging info, and print output to file
    def printout(self, sourcelist, translist, targetlist):

      self.print_alignment_statistics(len(sourcelist), len(targetlist))

      sources = []
      translations = []
      targets = []
      sources_factored = []
      targets_factored = []
      if self.options['factored']:
        sources_output = sources_factored
        targets_output = targets_factored
      else:
        sources_output = sources
        targets_output = targets

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

        lastsrc = src[-1]
        lasttarget = target[-1]

        translations.append(' '.join([translist[ID] for ID in src]))
        if self.options['factored']:
            sources.append(' '.join([sourcelist[ID][0] for ID in src]))
            targets.append(' '.join([targetlist[ID][0] for ID in target]))
            sources_factored.append(' '.join([sourcelist[ID][1] for ID in src]))
            targets_factored.append(' '.join([targetlist[ID][1] for ID in target]))

        else:
            sources.append(' '.join([sourcelist[ID] for ID in src]))
            targets.append(' '.join([targetlist[ID] for ID in target]))

        if self.options['filter'] == 'sentences':
            self.check_sentence_pair(j, sources[-1], translations[-1], targets[-1], sources_output[-1], targets_output[-1], sentscores)

      if self.options['filter'] == 'sentences':
              self.filter_sentence_pairs(sentscores, sources_output, targets_output)

      if self.options['filter'] == 'articles':
        self.filter_article_pairs(sources, translations, targets, sources_output, targets_output)

      self.log("\nfinished with article",1)
      self.log("\n====================\n",1)

      if self.out1 and self.out2 and not self.options['filter']:
        if self.options['factored']:
            self.out1.writelines([line + '\n' for line in sources_factored])
            self.out2.writelines([line + '\n' for line in targets_factored])
        else:
            self.out1.writelines([line + '\n' for line in sources])
            self.out2.writelines([line + '\n' for line in targets])


    #get BLEU score of sentence pair (for filtering)
    def check_sentence_pair(self, j, src, trans, target, source_out, target_out, sentscores):

          sentscore = self.score_article([trans],[target])
          sentscore2 = self.score_article([src],[target])
          if sentscore2 > sentscore and self.options['filterlang']:
            self.out_bad1.write(source_out + '\n')
            self.out_bad2.write(target_out + '\n')
          else:
            if sentscore > 0:
              sentscorex = self.score_article([target],[trans])
              newsentscore = (2*sentscore*sentscorex)/(sentscore+sentscorex)
            else:
              newsentscore = 0
            sentscores[j]=newsentscore


    # get BLEU score for article pair
    def score_article(self,test,ref):
      refs = [bleu.cook_refs([refSent],self.options['bleu_ngrams']) for refSent in ref]
      testcook = []

      for i,line in enumerate(test):
        testcook.append(bleu.cook_test(line,refs[i],self.options['bleu_ngrams']))

      score = bleu.score_cooked(testcook,self.options['bleu_ngrams'])
      return score


    # store BLEU score for each sentence pair (used for filtering at the very end)
    def filter_sentence_pairs(self, sentscores, sources_output, targets_output):
        before = len(self.sources_out)
        for j,(src,target) in enumerate([i[0] for i in self.multialign]):
            if j in sentscores: # false if sentence pair has been filtered out by language filter
                confidence = sentscores[j]
                self.finalbleu.append((confidence,sentscores.get(j),before,before+1))
                before += 1
                self.sources_out.append(sources_output[j])
                self.targets_out.append(targets_output[j])


    # store BLEU score for each article pair (used for filtering at the very end)
    def filter_article_pairs(self, sources, translations, targets, sources_output, targets_output):
        articlescore = self.score_article(translations,targets)
        articlescore2 = self.score_article(sources,targets)

        self.log('\nBLEU score for article: ' + str(articlescore) + ' / ' + str(articlescore2),1)

        if articlescore2 > articlescore and self.options['filterlang']:
            if self.options['factored']:
                sources,targets = sources_factored,targets_factored
            for i,line in enumerate(sources):
                self.out_bad1.write(line + '\n')
                self.out_bad2.write(targets[i] + '\n')
        else:
            articlescorex = self.score_article(targets,translations)
            if articlescore > 0:
                articlescore = (articlescore*articlescorex*2)/(articlescore+articlescorex)
            before = len(self.sources_out)
            after = before + len(self.multialign)
            self.finalbleu.append((articlescore,articlescore2,before,after))

            self.sources_out += sources_output
            self.targets_out += targets_output


    #filter bad sentence pairs / article pairs
    def write_filtered(self):
      
      self.finalbleu = sorted(self.finalbleu,key=itemgetter(0),reverse=True)
      self.log(self.finalbleu,2)
      
      totallength=0
      totalscore=0
      
      for (articlescore,articlescore2,before,after) in self.finalbleu:
        length = after-before
        totallength += length
        totalscore += articlescore*length
        
      averagescore = totalscore/totallength
      self.log("The average BLEU score is: " + str(averagescore),1)
      
      goodlength = totallength*self.options['filterthreshold']/float(100)
      totallength = 0
      
      bad_percentiles = []
      for i,(articlescore,articlescore2,before,after) in enumerate(self.finalbleu):
        length = after-before
        totallength += length
        if totallength > goodlength:
          bad_percentiles = self.finalbleu[i+1:]
          self.log("\nHow about throwing away the following " + self.options['filter'] + "?\n",2)
          self.log(bad_percentiles,2)
          if self.options['verbosity'] >= 3:
            for score,score2,start,end in bad_percentiles:
              for i in range(start,end):
                self.log(score,3)
                self.log(self.sources_out[i],3)
                self.log(self.targets_out[i],3)
                self.log('-----------------',3)
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

    #close all files opened by __init__
    def close_file_streams(self):
        if self.close_src:
            self.src.close()
        if self.close_target:
            self.target.close()
        if self.close_out1:
            self.out1.close()
        if self.close_out2:
            self.out2.close()
        if self.close_out_bad1:
            self.out_bad1.close()
        if self.close_out_bad2:
            self.out_bad2.close()
        for should_be_closed,output_stream\
                in zip(self.close_srctotarget,self.srctotarget):
            if should_be_closed:
                output_stream.close()
        for should_be_closed,output_stream\
                in zip(self.close_targettosrc,self.targettosrc):
            if should_be_closed:
                output_stream.close()

    def log(self, msg, level = 1, end='\n'):
      if level <= self.options['verbosity']:
        print(msg, end=end, file = self.options['log_to'])

#Allows parallelizing of alignment
if multiprocessing_enabled:
  class AlignMultiprocessed(multiprocessing.Process,Aligner):

    def __init__(self,tasks,options,scores,log):
      multiprocessing.Process.__init__(self)
      self.options = options
      self.tasks = tasks
      self.scores = scores
      self.log = log
      self.bleualign = []
      self.scoredict = None

    def run(self):
      
      i,data = self.tasks.get()
      while i != None:

        self.log('reading in article ' + str(i) + ': ',1)
        sourcelist,targetlist,translist1,translist2 = data
        self.multialign = self.process(sourcelist,targetlist,translist1,translist2)
        self.scores[i] = (data,self.multialign,self.bleualign,self.scoredict)
        
        i,data = self.tasks.get()
