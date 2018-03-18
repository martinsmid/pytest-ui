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
        'attrs==17.4.0',
        'future==0.16.0',
        'pluggy==0.6.0',
        'py==1.5.2',
        'pytest==3.4.1',
        'six==1.11.0',
        'tblib==1.3.2',
        'urwid==2.0.1',
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
