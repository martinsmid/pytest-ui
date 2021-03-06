#!/usr/bin/env python3
import sys
import shutil
import doit
import subprocess
from git import Repo

def get_release_tag():
    """ Ask user for release tag and return it """
    repo = Repo('.')
    repo.tags
    current_tag = next((tag for tag in repo.tags if tag.commit == repo.head.commit), None)
    if current_tag:
        use_current = input(f'Use current tag "{current_tag.name}" for release ? [y/n] : ')
        if use_current == 'y':
            return current_tag.name

    # print all/previous release tags
    output = subprocess.check_output(['git', 'tag', '--list', 'v*']).decode()
    print(f""" -- Existing release tags : \n{output}""")
    release_tag = input('Enter release tag : ')
    confirmed = input(f'Confirm release tag {release_tag} [y/n] : ')
    if confirmed != 'y':
        return False

    return release_tag


def run_setup_build():
    subprocess.run(["python", "setup.py", "sdist", "bdist_wheel"])


def prepare():
    # check current branch
    repo = Repo('.')
    if repo.active_branch.name != 'master':
        print(f'You are in "{repo.active_branch.name}" branch. Switch to master for release.')
        sys.exit(1)

def build():
    # get release tag
    release_tag = get_release_tag()
    changelog_tag = release_tag[1:]
    # check changelog
    cmd = subprocess.run(["grep", f'{changelog_tag}', "CHANGELOG.md"])
    if cmd.returncode != 0:
        print(f'Update CHANGELOG.md. Current release tag "{release_tag}" not found.')
        sys.exit(2)

    # tag release
    subprocess.run(["git", "tag", release_tag])

    # clean build dir
    shutil.rmtree('dist')

    # build
    run_setup_build()
    return True


def publish(pypi_repo_name):
    # push tags
    subprocess.run(["git", "push", "--tags"])

    print(pypi_repo_name)
    # upload to pypi
    subprocess.run(["twine", "upload", "-r", pypi_repo_name, "dist/*"])

    return True


def info(live):
    _type = 'live' if live else 'test'
    print(f'Doing a {_type} release.')


def task_release(live=False):
    """ Build a package. Prepare files for upload. """
    pypi_repo_name = 'pypi' if live else 'pypitest'

    return {
        'actions': [
            info,
            prepare,
            build,
            (publish, [pypi_repo_name]),
        ],
        'params': [
            {
                'name': 'live',
                'long': 'live',
                'help': 'make a real release, not a test',
                'type': bool,
                'default': False
            }
        ],
        'verbosity': 2,
    }

if __name__ == '__main__':
    doit.run(globals())
