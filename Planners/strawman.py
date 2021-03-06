#! /Users/rkrsn/miniconda/bin/python
from __future__ import print_function, division
from numpy import array, asarray, mean, median, percentile, size, sum, sqrt
from pdb import set_trace
from tools.misc import *
from tools.rforest import *
from tools.where import where
import pandas as pd
from sklearn.tree import DecisionTreeClassifier as CART
from scipy.spatial.distance import euclidean as edist

def flatten(x):
  """
  Takes an N times nested list of list like [[a,b],[c, [d, e]],[f]]
  and returns a single list [a,b,c,d,e,f]
  """
  result = []
  for el in x:
    if hasattr(el, "__iter__") and not isinstance(el, basestring):
      result.extend(flatten(el))
    else:
      result.append(el)
  return result


class changes():

  def __init__(self):
    self.log = {}

  def save(self, name=None, old=None, new=None):
    if not old == new:
      self.log.update({name: (old, new)})

class node():

  """
  A data structure to hold all the rows in a cluster.
  Also return an exemplar: the centroid.
  """

  def __init__(self, rows):
    self.rows = []
    for r in rows:
      self.rows.append(r[:-1])

  def exemplar(self, what='centroid'):
    if what == 'centroid':
      return median(array(self.rows), axis=0)
    elif what == 'mean':
      return mean(array(self.rows), axis=0)


class contrast():

  "Identify the nearest enviable node."

  def __init__(self, clusters, norm):
    self.clusters = clusters
    self.norm = norm

  def closest(self, testCase):
    return sorted([f for f in self.clusters],
                  key=lambda F: edist(F.exemplar(), testCase[:-1]))[0]

  def envy(self, testCase, alpha=0.5):
    me = self.closest(testCase)
    others = [o for o in self.clusters if not me == o]
    betters = [f for f in others if f.exemplar()[-1] < alpha*me.exemplar()[-1]]
    try:
      return sorted([f for f in betters],
                    key=lambda F: edist(F.exemplar()/self.norm, me.exemplar()/self.norm))[0]
    except:
      return me


class patches():

  "Apply new patch."

  def __init__(
          self, train, test, clusters, prune=False, B=0.25
          , verbose=False, config=False, models=False, pred=[], name=None):

    self.train = csv2DF(train)
    self.trainBIN = csv2DF(train,toBin=True)
    self.test = csv2DF(test)
    self.name = name
    self.clusters = clusters
    self.Prune = prune
    self.B = B
    self.mask = self.fWeight()
    self.write = verbose
    self.bin = config
    self.pred = pred
    self.change = []

  def min_max(self):
    allRows = pd.concat([self.train, self.test]).as_matrix()
    return np.max(allRows, axis=0)[:-1]-np.min(allRows, axis=0)[:-1]

  def fWeight(self, criterion='Variance'):
    "Sort "
    clf = CART(criterion='entropy')
    features = self.train.columns[:-1]
    klass = self.train[self.train.columns[-1]]
    clf.fit(self.train[features], klass)
    lbs = clf.feature_importances_
    if self.Prune:
      cutoff = sorted(lbs, reverse=True)[int(len(lbs)*self.B)]
      return np.array([cc if cc>=cutoff else 0 for cc in lbs])
    else:
      return lbs

  def delta(self, t):

    C = contrast(self.clusters, norm=self.min_max())
    closest = C.closest(t)
    better = C.envy(t, alpha=1)
    def delta0(node1, node2):
      if not self.bin:
        return array([el1 - el2 for el1
        , el2 in zip(node1.exemplar(), node2.exemplar())])*self.mask
      else:
        return array([el1 == el2 for el1
        , el2 in zip(node1.exemplar(), node2.exemplar())])
    return delta0(closest, better)

  def patchIt(self, t):
    C = changes()
    if not self.bin:
      for i, old, delt in zip(range(len(t[:-1])), t[:-1], self.delta(t)):
        C.save(self.train.columns[i][1:], old, new=old + delt)
      self.change.append(C.log)
      indep = pd.DataFrame((array(t[:-1]) + self.delta(t)).tolist()+[t[-1]])
      _, depen = rforest(self.trainBIN, indep.transpose())
      return indep.transpose().as_matrix()[0].tolist()[:-1]+[depen[0]]
    else:
      for i, old, delt, m in zip(range(len(t.cells[:-2])), t.cells[:-2], self.delta(t), self.mask.tolist()):
        C.save(
            self.train.headers[i].name[
                1:],
            old,
            new=(
                1 -
                old if delt and m > 0 else old))
      self.change.append(C.log)
      return [1 - val if d and m > 0 else val for val, m,
              d in zip(t.cells[:-2], self.mask, self.delta(t))]

  def newTable(self, justDeltas=False):
    if not self.bin:
      newRows = [self.patchIt(t) for t in self.test.as_matrix() if t[-1]>0]
    else:
      newRows = [self.patchIt(t) if t[-1]>0 else t.tolist() for t in self.test.as_matrix()]
    after = pd.DataFrame(newRows, columns=self.test.columns)
    if not justDeltas:
      return after
    else:
      return self.change

class strawman():
  def __init__(self, train, test, name=None, prune=False):
    self.train, self.test = train, test
    self.prune = prune
    self.name = name

  def main(self, mode='defect', justDeltas=False):
    if mode == "defect":
      train_DF = csv2DF(self.train)
      test_DF = csv2DF(self.train)
      before = rforest(train=train_DF, test=test_DF)
      clstr = [node(c) for c in where(data=train_DF)]
      return patches(train=self.train,
                     test=self.test,
                     clusters=clstr,
                     prune=self.prune,
                     pred=before).newTable(justDeltas=justDeltas)

if __name__ == '__main__':
  for name in ['ivy', 'jedit', 'lucene', 'poi', 'ant']:
    train, test = explore(dir='../Data/Jureczko/', name=name)
    aft = strawman(train, test, prune=True).main()
    # _, pred = rforest(train,aft)
    # _,  bef = rforest(train,csv2DF(test))
    testDF = csv2DF(test, toBin=True)
    before = testDF[testDF.columns[-1]]
    after = aft[aft.columns[-1]]
    print(name,':%0.2f'%((1-sum(after)/sum(before))*100))
  set_trace()

