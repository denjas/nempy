#!/usr/bin/env python

import json
import os
import importlib.util

from setuptools import setup, find_packages

module_dir = os.path.dirname(os.path.abspath(__file__))


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


def get_packages_from_pipfile_lock(path: str, version):
    version = f'=={version}'
    with open(path, "r") as read_file:
        data = json.load(read_file)
        packages_list = [f"{item[0]}{item[1].get('version', version)}" for item in data['default'].items()]
        packages = '\n'.join(packages_list)
        return packages


spec = importlib.util.spec_from_file_location('nempy', 'src/nempy/__init__.py')
nempy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nempy)
version = nempy.__version__
package_name = nempy.__package_name__

setup(
    name=package_name,
    version=version,
    python_requires='>=3.6.0',
    author="Denys Shcheglov",
    author_email='ikuzen@gmail.com',
    description='High-level wrapper for working with cryptocurrencies of the NEM ecosystem',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/DENjjA/nempy',
    project_urls={"Bug Tracker": "https://github.com/DENjjA/nempy/issues", },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=(find_packages(where="src")),
    # install_requires=open('requirements.txt').read(),
    install_requires=get_packages_from_pipfile_lock('Pipfile.lock', version),
    scripts=['src/nempy/bin/nempy-cli.py', ],
    test_suite='tests',
    include_package_data=True
)
