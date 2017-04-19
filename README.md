
# Introduction

The ox_herd package is a python system for job scheduling and management based on the [python-rq](http://python-rq.org) package.

The main goal of ox_herd is to make it easy to schedule, inspect, and administrate automated jobs including:

  1. Running tests via [pytest](https://docs.pytest.org/en/latest/).
  1. Running [pylint](https://www.pylint.org/) on your code.
  1. Running arbitrary python scripts.

# Comparisons

Some other alternatives for python include Celery and python rq.  The ox_herd package is intended to be light-weight as compared to something more full featured and sophisticated like Celery. It is based on and built on top of python rq so it is a little more heavy-weight than rq. Ideally, it provides the minimal set of features and frameworks on top of rq for web based task monitoring, customization, and analysis for your rq tasks.

# Documentation

See the full [documentation on github](https://github.com/aocks/ox_herd/blob/master/docs/intro.md) for further details. 

