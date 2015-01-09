from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()

version = '0.1.10'

install_requires = [
    "toml==0.8.1",
    "provtool==0.3.0",
    "biplist==0.6",
]

setup(name='fox',
    version=version,
    description="An Xcode build tool and utility knife.",
    long_description=README,
    classifiers=[
      # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      'Programming Language :: Python :: 2.7',
      ],
    keywords='xcode',
    author='Andy Mroczkowski',
    author_email='andy@mrox.net',
    url='http://github.com/amrox/fox',
    license='BSD',
    packages=find_packages('fox', exclude=['ez_setup', 'examples', 'tests']),
    package_dir={'fox': 'fox'}, include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    entry_points={
        'console_scripts':
            ['fox=fox.cli:main']
    }
)
