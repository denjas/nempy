#!/usr/bin/env python

import json

from setuptools import setup, find_packages

from nempy import __version__


def get_packages_from_pipfile_lock(path: str):
    with open(path, "r") as read_file:
        data = json.load(read_file)
        packages_list = [f"{item[0]}{item[1]['version']}" for item in data['default'].items()]
        packages = '\n'.join(packages_list)
        return packages


setup(
    name='nempy',
    version=__version__,
    python_requires='>=3.9.0',
    packages=(find_packages()),
    description='{package description}',
    long_description=open('README.md').read(),
    url='https://git.eosda.com/common',
    install_requires=get_packages_from_pipfile_lock('Pipfile.lock'),
    scripts=['cli/nempy-cli.py', ],
    test_suite='tests',
    include_package_data=True
)
