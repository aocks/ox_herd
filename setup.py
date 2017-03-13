"""A setuptools based setup module for ox_herd

Copyright (c) 2016, Emin Martinian - All Rights Reserved
Unauthorized copying of this file, via any medium is strictly prohibited
See LICENSE at the top-level of this distribution for more information
or write to emin.martinian@gmail.com for more information.
"""

# see also setup.cfg

from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='ox_herd',
    version='0.1.0',

    description='Tools for distributed testing and integration.',
    long_description=long_description,
    url='http://github.com/aocks/ox_herd',
    author='Emin Martinian',
    author_email='emin.martinian@gmail.com',
    license='custom',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
    ],


    keywords='testing continuous integration', 
    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']), #FIXME
    install_requires=[], #FIXME: need more here
    # If there are data files included in your packages that need to be
    # installed, specify them here.
    package_data={
        'sample': ['package_data.dat'],
    },
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'sample=sample:main',
        ],
    },
)
