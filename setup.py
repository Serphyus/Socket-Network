from setuptools import setup, find_packages
import msgpack

setup(
    name='socket_network',
    version='0.0.1',
    author='Serphyus',
    packages=find_packages(),
    package_dir={'': 'source'},
    install_requires=[
        'msgpack>=1.0.2'
    ]
)


"""
Requirements
============
dill
"""