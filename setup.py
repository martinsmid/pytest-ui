from setuptools import setup

setup(
    name='pytest-ui',
    description='Text User Interface for running python tests',
    version='0.1',
    license='MIT',
    platforms=['linux', 'osx', 'win32'],
    packages=['pytui'],
    url='https://github.com/martinsmid/pytest-ui',
    author_email='martin.smid@gmail.com',
    author='Martin Smid',
    entry_points={
        'pytest11': [
            'pytui = pytui.runner',
        ]
    },
    install_requires=['urwid>=1.3.1,pytest>=3.0.5'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS :: MacOS X',
        'Topic :: Software Development :: Testing',
        'Topic :: Utilities',
        'Programming Language :: Python', ],
)
