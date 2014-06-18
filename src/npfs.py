#!/usr/bin/env python
import numpy as np
import feast 
from scipy.stats import binom
from multiprocessing import Pool
import matplotlib.pylab as plt

__author__ = "Gregory Ditzler"
__copyright__ = "Copyright 2014, EESI Laboratory (Drexel University)"
__credits__ = ["Gregory Ditzler"]
__license__ = "GPL"
__version__ = "0.1.0"
__maintainer__ = "Gregory Ditzler"
__email__ = "gregory.ditzler@gmail.com"
__status__ = "development"

class npfs:

  def __init__(self, fs_method="JMI", n_select=5, n_bootstraps=100, \
      verbose=False, alpha=.01, beta=0.0, parallel=None, min_improv=0.):
    """     
    @self - self explanitory
    @fs_method - feature selection algorithm to use. Available methods are: 
      CIFE, CMIM, CONDMI, CONDRED, DISR, ICAP, JMI, MIM, MIFS, mRMR
      DEFAULT: JMI
    @n_select - number of features to select. this is the number of 
      features that the base feature selection uses. NPFS may 
      select a different number of features [DEFAULT = 5]
    @n_bootstraps - number of bootstraps [DEFAULT = 100]
    @alpha - size of the hypothesis test [DEFAULT = 0.01]
    @beta - bias parameter for the test [DEFAULT = 0.0]
    @parallel - number of parallel workers to use [DEFAULT = None]
    @min_improv - critera for early stopping [DEFAULT = 0.0]
    """
    self.fs_method = fs_method
    self.n_select = n_select
    self.n_bootstraps = n_bootstraps
    self.alpha = alpha
    self.beta = beta
    self.selected_features = []
    self.parallel = parallel
    self.min_improv = min_improv
    if min_improv != 0.:
      self.early_stopping = True 
    else:
      self.early_stopping  = False 

  def fit(self, data, labels):
    """
    @self - self explanitory
    @data - data in a numpy array. here are some suggestions for formatting 
      the data. 
      len(data) = n_observations
      len(data.transpose()) = n_features
    @labels - numerical class labels in a numpy array. 
      len(labels) = n_observations
    """
    data, labels = self.__check_data(data, labels)
    try: 
      fs_method = getattr(feast, self.fs_method)
    except ImportError: 
      raise("Method does not exist in FEAST")

    self.n_observations = len(data)
    self.n_features = len(data.transpose())
    self.method = fs_method

    # @Z - contains the observations of the Bernoulli random variables
    #      that are whether the feature were or were not selected 
    Z = np.zeros( (self.n_features, self.n_bootstraps) )
    self.data = data
    self.labels = labels

    if self.parallel == None: 
      if self.early_stopping == False: 
        for b in range(self.n_bootstraps):
          sf = self.boot_iteration()
          Z[sf, b] = 1  # mark the features selected with a '1'.
      else:
        p1_old = np.zeros((self.n_features,))
        for b in range(self.n_bootstraps):
          sf = self.boot_iteration()
          Z[sf, b] = 1.

          p1 = Z.sum(axis=1)/b
          d = np.abs(p1 - p1_old).mean()
          if d < self.min_improv:
            self.run_time = b
            break
          p1_old = p1

    else:
      pool = Pool(processes = self.parallel)
      sfs = pool.map(__call__, (self for x in range(self.n_bootstraps)))
      for x in range(len(sfs)):
        Z[sfs[x], x] = 1

    z = np.sum(Z, axis=1)  # z is a binomial random variable
    # compute the neyman-pearson threshold (include the bias term)
    p = (1.0*self.n_select)/self.n_features + self.beta
    if p > 1.0: # user chose \beta poorly -- null it out
      raise ValueError("p+beta > 1 -> Invalid probability")

    delta = binom.ppf(1 - self.alpha, self.n_bootstraps, p)
    # based on the threshold, determine which features are relevant and return
    # them in a numpy array 
    selected_features = []
    for k in range(self.n_features):
      if z[k] > delta:
        selected_features.append(k)

    self.Bernoulli_matrix = Z
    self.selected_features = np.array(selected_features)
    return self.selected_features

  def __check_data(self, data, labels):
    """
      The data and label arrays must be of the same length. Furthermore, 
      the data are expected to be in numpy arrays. Return an error if this
      is not the case. Otherwise, if everything else check out, cast the
      arrays as floats. Its how the data are expected for PyFeast.
    """
    if isinstance(data, np.ndarray) is False:
      raise Exception("Data must be an numpy ndarray.")
    if isinstance(labels, np.ndarray) is False:
      raise Exception("Labels must be an numpy ndarray.")
    if len(data) != len(labels):
      raise Exception("Data and labels must be the same length")
    return 1.0*data, 1.0*labels

  def boot_iteration(self, null=None):
    """
    @self
    @null - leave alone
    """
    # generate some random integers that are the boostrap indices. the size
    # of the bootstrap is the size of the data sample. hence all samples are 
    # sampled with replacement
    idx = np.random.randint(0, self.n_observations, self.n_observations)
    data_sub = self.data[idx]      # bootstrap features
    labels_sub = self.labels[idx]  # bootstrap labels
    sf = self.method(data_sub, labels_sub, self.n_select) # run feature selection
    return sf

  def plot_bernoulli_matrix(self, show_npfs=False):
    """
    Plot the heatmap of the Bernoulli matrix 
    @self
    @show_npfs - Highlight NPFS detections [Boolean] 
    """
    matrix = self.Bernoulli_matrix
    if show_npfs == False:
      plot = plt.imshow(matrix)
      plot.set_cmap('hot')
      plt.colorbar()
      plt.xlabel("Bootstraps")
      plt.ylabel("Feature")
      plt.show()
    else:
      for i in self.selected_features:
        for k in range(len(matrix[i])):
          matrix[i,k] = .5
      plot = plt.imshow(matrix)
      plot.set_cmap('hot')
      plt.xlabel("Bootstraps")
      plt.ylabel("Feature")
      plt.colorbar()
      plt.show()
    return None

def __call__(obj):
  """
  This is a weird little hack to get around using multiprocessing with 
  the package being called inside of the NPFS object 
  """
  return obj.boot_iteration(None)
