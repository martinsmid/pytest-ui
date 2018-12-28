from setuptools import setup

from pytui.settings import VERSION


setup(
    name='pytest-ui',
    description='Text User Interface for running python tests',
    version=VERSION,
    license='MIT',
    platforms=['linux', 'osx', 'win32'],
    packages=['pytui'],
    url='https://github.com/martinsmid/pytest-ui',
    author_email='martin.smid@gmail.com',
    author='Martin Smid',
    entry_points={
        'console_scripts': [
            'pytui = pytui.ui:main',
        ]
    },
    install_requires=[
        'future',
        'pytest',
        'tblib',
        'urwid',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS :: MacOS X',
        'Topic :: Software Development :: Testing',
        'Topic :: Utilities',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
)
