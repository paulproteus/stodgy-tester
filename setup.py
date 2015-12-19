#!/usr/bin/env python

from setuptools import setup, find_packages

DESCRIPTION = ('Run command line test suites in a virtual machines, '
               'with the help of Vagrant and qemu.')

setup(
    name='stodgy-tester',
    version='0.0.1',
    description=DESCRIPTION,
    author='Asheesh Laroia',
    author_email='asheesh@sandstorm.io',
    install_requires=[
        'ansicolor',
        'pexpect',
    ],
    entry_points={
        'console_scripts': [
            'stodgy-tester = stodgy_tester:main',
        ],
    },
    packages=find_packages(),
)
