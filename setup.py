#!/usr/bin/env python
# coding: utf-8

from setuptools import setup, find_packages


VERSION = '0.4.0'
REQS = [
    'lxml',
    'requests',
    'PyYAML',
    'click',
    'requests-oauthlib',
    'flask',
    'tabulate',
]


setup(
    name='inoreader',
    version=VERSION,
    description='Python wrapper of Inoreader API',
    license='MIT',
    packages=find_packages(),
    install_requires=REQS,
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': ['inoreader=inoreader.main:main']
    },
)
