from setuptools import setup, find_packages


setup(
    name='socket_network',
    version='0.0.1',
    author='Serphyus',
    packages=find_packages(),
    package_dir={'': 'source'},
    install_requires=[
        'dill>=0.3.3'
    ]
)


"""
Requirements
============
dill
"""