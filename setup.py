import codecs
import os
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


if len(sys.argv) <= 1:
    print("""
Suggested setup.py parameters:
    * build
    * install
    * sdist  --formats=zip
    * sdist  # NOTE requires tar/gzip commands

PyPi:

    twine upload dist/*

""")

package_root = os.path.abspath(os.path.dirname(__file__))

readme_filename = os.path.join(package_root, 'README.md')
if os.path.exists(readme_filename):
    with codecs.open(readme_filename, encoding='utf-8') as f:
        long_description = f.read()
else:
    long_description = None

setup(
    name='modtpy',
    author="dominikandreas",
    version="0.1",
    description='Python API + CLI for controlling your New Matter Mod-T 3D printer',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/dominikandreas/modtpy',
    author_email='',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='home automation',
    include_package_data=True,
    packages=['modtpy', 'modtpy.cli'],
    platforms=['linux', ],
    install_requires=[
        'pyusb',
        'click',  # optional
        'tqdm',
    ],
    entry_points={
        'console_scripts': ['modtpy=modtpy.cli:cli_root'],
    }
)
