from setuptools import setup, find_packages

# Basic information
VERSION = '0.1.0' # Initial version
DESCRIPTION = 'A CLI tool for archiving webnovels'
LONG_DESCRIPTION = 'This package provides a command-line interface to archive webnovels from various sources.'

# Define requirements
# Read from requirements.txt, but filter out comments and empty lines
try:
    with open('requirements.txt', encoding='utf-8') as f:
        install_requires = [line.strip() for line in f if line.strip() and not line.startswith('#')]
except FileNotFoundError:
    install_requires = [] # Or define a minimal set here if requirements.txt is optional

setup(
    name='webnovel-archiver',
    version=VERSION,
    author='Your Name / Project Team', # Placeholder - user should update
    author_email='your.email@example.com', # Placeholder - user should update
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    packages=find_packages(include=['webnovel_archiver', 'webnovel_archiver.*']), # Find packages under webnovel_archiver
    install_requires=install_requires, # List of dependencies
    entry_points={
        'console_scripts': [
            'archiver = webnovel_archiver.cli.main:archiver',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha', # Or another appropriate status
        'Intended Audience :: End Users/Desktop',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'Topic :: Utilities',
    ],
    python_requires='>=3.7', # Example Python version requirement
)
