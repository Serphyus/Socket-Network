from setuptools import setup, find_packages
from importlib import import_module

version = import_module('src.socket_network._version')

setup(
    name='socket_network',
    version=version.__version__,
    author='Serphyus',
    packages=find_packages(),
    package_dir={'': 'src'},
    install_requires=[
        'msgpack>=1.0.2'
    ]
)