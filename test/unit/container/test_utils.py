import os
import shutil
import tempfile
import unittest
from os import path

import pytest

from container.common.exceptions import AnsibleContainerNotInitializedException
from container.common.utils import assert_initialized


class TestMissingFiles(unittest.TestCase):

    '''
    This test class creates a temporary folder with only "main.yml"
    written out. This tests passses if AnsibleContainerNotInitializedException
    is correctly raised due to a missing 'container.yml' file.
    '''

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ansible_dir = path.join(self.test_dir, "ansible")
        os.mkdir(self.ansible_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_something(self):
        f = open(path.join(self.ansible_dir, 'main.yml'), 'w')
        f.write('')
        with pytest.raises(AnsibleContainerNotInitializedException):
            assert_initialized(self.test_dir)
