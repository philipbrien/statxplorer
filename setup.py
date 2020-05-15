# -*- coding: utf-8 -*-
"""
Setup for statxplorer
"""
from setuptools import setup
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md'), encoding='utf-8') as readme_file:
    full_description = readme_file.read()
    
setup(
      name="statxplorer",
      version="0.1",
      description="Python interface to the UK Government Department for Work "
                  "and Pensions' Stat-Xplore data service",
      long_description=full_description,
      long_description_content_type='text/markdown',
      url="https://github.com/philipbrien/statxplorer",
      author="Philip Brien",
      author_email="brienp@parliament.uk",
      classifiers=["Development Status :: 3 - Alpha",
                   "Programming Language :: Python :: 3"],
      py_modules="statxplorer.py",
      python_requires='>=3',
      install_requires=['pandas', 'requests'])