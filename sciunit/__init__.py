import inspect

"""SciUnit: A Test-Driven Framework for Validation of 
     Quantitative Scientific Models"""
import sciunit._tables as _tables

class Error(Exception):
  """Base class for errors in sciunit's core."""

#
# Tests
#
class Test(object):
  """Abstract base class for tests."""
  def __init__(self, observation, name=None, **params):
      if name is None:
        name = self.__class__.__name__
      self.name = name
      
      if self.description is None:
        self.description = self.__class__.__doc__
      
      self.params = params
      
      self.observation = observation
      self.validate_observation(observation)

      if self.score_type is None or not issubclass(self.score_type, Score):
        raise Error("Test %s does not specify a score type." % self.name)

  name = None
  """The name of the test. Defaults to the test class name."""

  description = None
  """A description of the test. Defaults to the docstring for the class."""

  observation = None
  """The empirical observation that the test is using."""

  params = None
  """A dictionary containing the parameters to the test."""

  def validate_observation(self, observation):
    """(Optional) Implement to validate the observation provided to the 
    constructor.

    Raises an ObservationError if invalid.
    """
    return True
  
  required_capabilities = ()
  """A sequence of capabilities that a model must have in order for the 
  test to be run. Defaults to empty."""

  def check_capabilities(self, model):
    """Checks that the capabilities required by the test are 
    implemented by `model`.

    Raises an Error if model is not a Model.
    Raises a CapabilityError if model does not have a capability.
    """
    if not isinstance(model, Model):
      raise Error("Model %s is not a sciunit.Model." % str(model))

    for c in self.required_capabilities:
      if not c.check(model):
        raise CapabilityError(model, c)

    return True

  def generate_prediction(self, model):
    """Generates a prediction from a model using the required capabilities.

    No default implementation.
    """
    raise NotImplementedError("Test %s does not implement generate_prediction."
       % str())

  score_type = None

  def compute_score(self, observation, prediction):
    """Generates a score given the observations provided in the constructor
    and the prediction generated by generate_prediction.

    Must generate a score of score_type.

    No default implementation.
    """
    raise NotImplementedError("Test %s does not implement compute_score."
      % self.name)

  def check(self, model, stop_on_error=True):
    """Like judge, but without actually running the test.
    Just returns a Score indicating whether the model can take the test or not."""
    e = None
    try:
      if self.check_capabilities(model):
        score = TBDScore(None)
      else:
        score = NAScore(None)
    except Exception as e:
      score = ErrorScore(e)
    if e and stop_on_error:
      raise e
    return score

  def _judge(self, model):
      # 1.
      self.check_capabilities(model)
      # 2.
      prediction = self.generate_prediction(model)
      self.last_model = model
      # 3.
      observation = self.observation
      score = self.compute_score(observation, prediction)
      # 4.
      if not isinstance(score, self.score_type):
        raise InvalidScoreError("Score for test '%s' is not of correct type." \
                                % self.name)
      # 5.
      score.model = model
      score.test = self
      score.prediction = prediction
      score.observation = observation
      return score
  
  def judge(self, model, stop_on_error=True, deep_error=False):
    """Generates a score for the provided model.

    Operates as follows:
    1. Checks if the model has all the required capabilities.
    2. Calls generate_prediction to generate a prediction.
    3. Calls score_prediction to generate a score.
    4. Checks that the score is of score_type, raising an InvalidScoreError.
    5. Equips the score with metadata:
       a) A reference to the model, in attribute model.
       b) A reference to the test, in attribute test.
       c) A reference to the prediction, in attribute prediction.
       d) A reference to the observation, in attribute observation.
    6. Returns the score.

    If stop_on_error is true (default), exceptions propagate upward. If false,
    an ErrorScore is generated containing the exception.
    """
    
    if deep_error:
      score = self._judge(model)
    else:
      try:
        score = self._judge(model)
      except CapabilityError as e:
        score = NAScore(str(e))
      except Exception as e:
        score = ErrorScore(e)
    if type(score) is ErrorScore and stop_on_error:
      raise score.score # An exception.  
    return score

  def __str__(self):
    #if self.params:
    #  x = "%s, %s" % (str(self.observation), str(self.params))
    #else:
    #  x = str(self.observation)
    #return "%s(%s)" % (self.name, x)
    return "%s (%s)" % (self.name, self.__class__.__name__)

  def __repr__(self):
    return str(self)

class ObservationError(Error):
  """Raised when an observation passed to a test is invalid."""

class CapabilityError(Exception):
  """Error raised when a required capability is not 
  provided by a model."""
  def __init__(self, model, capability):
    self.model = model
    self.capability = capability

    super(CapabilityError,self).__init__(\
      "Model %s does not provide required capability: %s" % \
      (model.name,capability.name))
  
  model = None
  """The model that does not have the capability."""

  capability = None
  """The capability that is not provided."""

class InvalidScoreError(Exception):
  """Error raised when a score is invalid."""

#
# Test Suites
#
class TestSuite(object):
  """A collection of tests."""
  def __init__(self, name, tests):
    if isinstance(tests, Test):
      # turn singleton test into a sequence
      tests = (tests,)
    else:
      try:
        for test in tests:
          if not isinstance(test, Test):
            raise Error("Test suite provided an iterable containing a non-Test.")
      except TypeError:
        raise Error("Test suite was not provided a test or iterable.")
    self.tests = tests

    if name is None:
      raise Error("Suite name required.")
    self.name = name

  name = None
  """The name of the test suite. Defaults to the class name."""

  description = None
  """The description of the test suite. No default."""

  tests = None
  """The sequence of tests that this suite contains."""

  def judge(self, models, stop_on_error=True):
    """Judges the provided models against each test in the test suite.

    Returns a ScoreMatrix.
    """
    if isinstance(models, Model):
      models = (models,)
    else:
      try:
        for model in models:
          if not isinstance(model, Model):
            raise Error("Test suite's judge method provided an iterable containing a non-Model.")
      except TypeError:
        raise Error("Test suite's judge method not provided a model or iterable.""")

    matrix = ScoreMatrix(self.tests, models)
    for test in self.tests:
      for model in models:
        matrix[test, model] = test.judge(model, stop_on_error)
    return matrix

  @classmethod
  def from_observations(cls, name, tests_info):
    """Instantiate a test suite with name 'name' and information about tests
    in 'tests_info', as [(TestClass1,observation1),(TestClass2,observation2),...].
    The desired test name may appear as an optional third item in the tuple, e.g.
    (TestClass1,observation1,"my_test").  The same test class may be used multiple 
    times, e.g. [(TestClass1,observation1a),(TestClass1,observation1b),...].
    """

    tests = []
    for test_info in tests_info:
      test_class = test_info[0]
      observation = test_info[1]
      test_name = None if len(test_info)<3 else test_info[2]
      assert inspect.isclass(test_class) and issubclass(test_class, Test), \
        "First item in each tuple must be a Test class"
      if test_name is not None:
        assert type(test_name) is str, "Each test name must be a string"
      tests.append(test_class(observation,name=test_name))
    return cls(name, tests)


#
# Scores
#
class Score(object):
  """Abstract base class for scores."""
  def __init__(self, score, related_data=None):
    if related_data is None:
      related_data = { }
    self.score, self.related_data = score, related_data
    if isinstance(score,Exception):
        self.__class__ = ErrorScore # Set to error score to use its summarize().
  
  score = None
  """The score itself."""

  description = ''
  """A description of this score, i.e. how to interpret it."""

  value = None
  """A raw number arising in a test's compute_score, 
  used to determine this score."""

  related_data = None
  """Data specific to the result of a test run on a model."""

  test = None
  """The test taken. Set automatically by Test.judge."""

  model = None
  """The model judged. Set automatically by Test.judge."""

  sort_key = None
  """A floating point version of the score used for sorting. 

  If normalized = True, this must be in the range 0.0 to 1.0,
  where larger is better (used for sorting and coloring tables)."""

  @property
  def summary(self):
    """Summarize the performance of a model on a test."""
    return "=== Model %s achieved score %s on test '%s'. ===" % \
      (str(self.model), str(self), self.test)

  def summarize(self):
    print((self.summary))

  def describe(self):
    if self.score is not None:
        print("The score was computed according to '%s' with raw value %s" % \
                 (self.description, self.value))

  def __str__(self):
    return '%s(%s)' % (self.__class__.__name__, self.score)

  def __repr__(self):
    return str(self)

class ErrorScore(Score):
    """A score returned when an error occurs during testing."""
    def __init__(self, exn, related_data=None):
        super(ErrorScore,self).__init__(exn, related_data)

    @property
    def summary(self):
      """Summarize the performance of a model on a test."""
      return "=== Model %s did not complete test %s due to error %s. ===" % \
        (str(self.model), str(self.test), str(self.score))

class NoneScore(Score):
    """A None score.  Indicates that the model has not been checked to see if
    it has the capabilities required by the test."""

    def __init__(self, score, related_data={}):
        if isinstance(score,Exception) or score is None:
            super(NoneScore,self).__init__(score, related_data=related_data)
        else:
            raise InvalidScoreError("Score must be None.")

class TBDScore(NoneScore):
    """A TBD (to be determined) score. Indicates that the model has capabilities 
    required by the test but has not yet taken it."""

    def __init__(self, score, related_data={}):
        super(TBDScore,self).__init__(score, related_data=related_data)
        
class NAScore(NoneScore):
    """A N/A (not applicable) score. Indicates that the model doesn't have the 
    capabilities that the test requires."""

    def __init__(self, score, related_data={}):
        super(NAScore,self).__init__(score, related_data=related_data)

#
# Score Matrices
#
class ScoreMatrix(object):
  """Represents a matrix of scores derived from a test suite.

  Should generally not be created or modified manually.

  Can use like this, assuming n tests and m models:

    >>> sm[test, model]
    score
    >>> sm[test]
    (score_1, ..., score_m)
    >>> sm[model]
    (score_1, ..., score_n)
  """
  def __init__(self, tests, models):
    self.tests = tests
    self.models = models

    self._matrix = matrix = { }
    for test in tests:
      column = matrix[test] = { }
      for model in models:
        column[model] = None

  def __getitem__(self, key):
    _matrix = self._matrix
    if isinstance(key, Test):
      return tuple(
        _matrix[key][model]
        for model in self.models)
    elif isinstance(key, Model):
      return tuple(
        _matrix[test][key]
        for test in self.tests)
    else:
      (test, model) = key
      return _matrix[test][model]

  def __setitem__(self, key, value):
    (test, model) = key
    if isinstance(test, Test) and isinstance(model, Model) \
       and isinstance(value, Score):
      self._matrix[test][model] = value
    else:
      raise Error("Expected (test, model) = score.")

  def view(self):
    """Generates an IPython score table."""
    return _tables.generate_ipy_table(self)

  def table_src(self):
    """Generates HTML source for the table view."""
    return _tables.generate_table(self)

#
# Models
#
class Model(object):
  """Abstract base class for sciunit models."""
  def __init__(self, name=None, **params):
    if name is None:
      name = self.__class__.__name__
    self.name = name
    self.params = params

  name = None
  """The name of the model. Defaults to the class name."""

  params = None
  """The parameters to the model (a dictionary).
  These distinguish one model of a class from another."""

  run_args = None
  """These are the run-time arguments for the model.
  Execution of run() should make use of these arguments."""

  def __str__(self):
    return "%s (%s)" % (self.name, self.__class__.__name__)

  def __repr__(self):
    return str(self)

#
# Capabilities
#
class Capability(object):
  """Abstract base class for sciunit capabilities."""
  @classmethod
  def check(cls, model):
    """Checks whether the provided model has this capability.

    By default, uses isinstance.
    """
    return isinstance(model, cls)

  class __metaclass__(type):
      @property
      def name(cls):
        return cls.__name__

  