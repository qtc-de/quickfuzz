import os
import shutil
import setuptools
from setuptools.command.develop import develop
from setuptools.command.install import install


def create_payloads_folder():
    '''
    quickfuzz ships a directory of payloads with the installation. This has to be
    copied into a path that is known by the quickfuzz executable. This is done by
    this function.

    Paramaters:
        None

    Returns:
        None

    Side-Effects:
        Creates a new shared folder inside ~/.local/share/
    '''
    user_home = os.path.expanduser("~")
    module_path = os.path.abspath(os.path.dirname(__file__)) + "/quickfuzz/"

    #creating the .local/share/quickfuzz folder
    share_dir = ".local/share/quickfuzz"
    if not os.path.isdir(f'{user_home}/{share_dir}'):
        os.makedirs(f'{user_home}/{share_dir}', exist_ok=True)

    #copying payloads_folder
    payloads_folder = f'{share_dir}/payloads'
    if not os.path.isdir(f'{user_home}/{payloads_folder}'):
        shutil.copytree(f'{module_path}/resources/payloads', f'{user_home}/{payloads_folder}')


def create_completion_folders():
    '''
    quickfuzz ships scripts for bash and zsh auto completion. These were copied to the
    desired locations in the users home by this function.

    Paramaters:
        None

    Returns:
        None

    Side-Effects:
        Creates completion files in the users home folder
    '''
    user_home = os.path.expanduser("~")
    module_path = os.path.abspath(os.path.dirname(__file__))

    #creating a .bash_completion.d directory
    config_dir = "/.bash_completion.d/"
    if not os.path.isdir(user_home + config_dir):
        os.makedirs(user_home + config_dir, exist_ok=True)

    #creating a .bash_completion file
    config_file = "/.bash_completion"
    if not os.path.isfile(user_home + config_file):
        shutil.copy(module_path + "/quickfuzz/resources/bash_completion", user_home + config_file)

    #creating bash autocomplete script
    config_file = config_dir + "quickfuzz"
    if not os.path.isfile(user_home + config_file):
        shutil.copy(module_path + "/quickfuzz/resources/bash_completion.d/quickfuzz", user_home + config_file)

    #creating a .zsh directory
    config_dir = "/.zsh/"
    if not os.path.isdir(user_home + config_dir):
        os.makedirs(user_home + config_dir, exist_ok=True)

    #creating zsh autocomplete script
    config_file = config_dir + "_quickfuzz"
    if not os.path.isfile(user_home + config_file):
        shutil.copy(module_path + "/quickfuzz/resources/zsh_completion.d/_quickfuzz", user_home + config_file)


class post_develop_command(develop):
    """
    Simple hook to do some additional stuff during installation

    Parameters:
        develop                 (Unkown)                Some argument provided by setup.py

    Returns:
        None

    Side Effects:
        None
    """
    def run(self):
        create_payloads_folder()
        create_completion_folders()
        develop.run(self)


class post_install_command(install):
    """
    Simple hook to do some additional stuff during installation

    Parameters:
        install                 (Unkown)                Some argument provided by setup.py

    Returns:
        None

    Side Effects:
        None
    """
    def run(self):
        create_payloads_folder()
        create_completion_folders()
        install.run(self)


with open("README.md", "r") as fh:
    long_description = fh.read()


setuptools.setup(

    name = "quickfuzz",
    author = "Tobias Neitzel",
    author_email = "",
    version = "1.0.0",
    url = f"https://github.com/qtc-de/quickfuzz",

    description = f"quickfuzz - quick service identification",
    long_description = long_description,
    long_description_content_type = "text/markdown",

    install_requires = [
                        "termcolor",
                       ],

    scripts = [
                'bin/quickfuzz',
              ],

    cmdclass={
                'develop': post_develop_command,
                'install': post_install_command,
            },

    packages = setuptools.find_packages(),
    package_data = {
                    'quickfuzz': [
                                    'resources/*',
                                    'resources/payloads/*',
                                    'resources/bash_completion.d/*',
                                    'resources/zsh_completion.d/*',
                                 ],
                   },
    classifiers = [
                    "Programming Language :: Python :: 3",
                    "Operating System :: Unix",
                  ],
)
