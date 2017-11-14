#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='Aiur',
        version='2.0',
        description='Aiur Replay Parser',
        author='Florian Meskens',
        author_email='f.meskens@eslgaming.com',
        url='https://www.eslgaming.com',
        packages=['aiur'],
        install_requires=['s2protocol'],
        dependency_links=[
            'https://github.com/Blizzard/s2protocol/tarball/master#egg=s2protocol'
            ]
        )
