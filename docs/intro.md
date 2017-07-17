
# Introduction

The ox_herd package is a python system for job scheduling and management based on the [python-rq](http://python-rq.org) package.

The main goal of ox_herd is to make it easy to schedule, inspect, and administrate automated jobs including:

  1. Running tests via [pytest](https://docs.pytest.org/en/latest/)
     * For example, you can use ox_herd as a simple, lightweight, dockerized continous integration server 
  1. Running [pylint](https://www.pylint.org/) on your code.
  1. Running arbitrary python scripts.

## Comparisons

Some other alternatives for python include Celery and python rq while more general solutions include things like Jenkins.  The ox_herd package is intended to be lightweight as compared to something more full featured and sophisticated like Celery. It is based on and built on top of python rq so it is a little more heavyweight than rq. Ideally, it provides the minimal set of features and frameworks on top of rq for web based task monitoring, customization, and analysis for your rq tasks.

## Documentation

See the full [documentation on github](https://github.com/aocks/ox_herd/blob/master/docs/intro.md) for further details. 

## Next Steps and Further Reading

See the following for more detailed discussions:

  1. [plugins.md](https://github.com/aocks/ox_herd/blob/master/docs/plugins.md): A discussion on how to write your own ox_herd plugins.

