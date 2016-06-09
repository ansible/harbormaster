from setuptools import setup, find_packages
from pip.req import parse_requirements
import container

install_reqs = parse_requirements('requirements.txt', session=False)
reqs = [str(ir.req) for ir in install_reqs]

setup(
    name='ansible-container',
    version=container.__version__,
    packages=find_packages(),
    include_package_data=True,
    url='https://github.com/ansible/ansible-container',
    license='LGPLv3 (See LICENSE file for terms)',
    author='Joshua "jag" Ginsberg and others (See AUTHORS file for contributors)',
    author_email='jag@ansible.com',
    description=('Ansible Container empowers you to orchestrate, build, run, and ship '
                 'Docker images built from Ansible playbooks.'),
    entry_points={
        'console_scripts': ['ansible-container = container.cli:commandline']
    },
    install_requires=reqs
)
